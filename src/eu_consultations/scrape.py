import os
from typing import List

import asyncio
from aiohttp_retry import RetryClient, ExponentialRetry
from loguru import logger
import srsly

from dataclass_wizard.errors import JSONWizardError

from eu_consultations.utils_scraping import (
    get_publication_id,
    get_feedback_info,
    convert_objectid_to_str,
    TOPICS,
    INITIATIVES_PAGE_SIZE,
    get_initiatives_ids,
    get_total_pages_initiatives,
)
from eu_consultations.consultation_data import Consultation


def show_available_topics():
    return TOPICS


async def async_scrape(
    topic_list: list,
    max_pages: int | None,
    max_feedback: int | None,
    stream_out_folder: str | os.PathLike | None = None,
) -> List[Consultation]:
    """Scrape consultation data from backend API of EU website

    Scrapes data from https://ec.europa.eu/info/law/better-regulation

    Args:
        topic_list: topics to scrape
        max_pages: set limit on number of pages to scrape.
        max_feedback: set limit on maximum of feedback to gather per consultation
        stream_out_folder: path to folder to stream out JSON per scraped page. defaults to None.
    Returns:
        A list of Consultation dataclass object
    """
    logger.info("starting scraping")
    consultations = []
    not_allowed_topics = [
        not_allowed for not_allowed in topic_list if not_allowed not in TOPICS.keys()
    ]
    if len(not_allowed_topics) > 0:
        logger.error(
            f"The topic(s) {' '.join(not_allowed_topics)} are not allowed topics. Topic must be one of {' '.join(TOPICS)}."
        )
        raise ValueError("topic list contains not allowed topics")
    for topic in topic_list:
        logger.info(f"scraping topic {topic}")
        total_pages = get_total_pages_initiatives(topic)
        page = 0

        semaphore = asyncio.Semaphore(10)
        retry_options = ExponentialRetry(attempts=5)

        async with RetryClient(
            raise_for_status=False, retry_options=retry_options
        ) as session:
            while True:
                id_list = await get_initiatives_ids(
                    session,
                    topic,
                    size=INITIATIVES_PAGE_SIZE,
                    language="en",
                    page=page,
                    semaphore=semaphore,
                )
                logger.info(
                    f"Processing page {page} of {total_pages} for topic {topic}"
                )
                if not id_list:
                    break
                pubid = await get_publication_id(
                    session, id_list, semaphore, max_feedback
                )
                feedback_info = await get_feedback_info(
                    session, pubid, topic, semaphore
                )
                # Convert ObjectId to string before saving to JSON
                feedback_info_str = convert_objectid_to_str(feedback_info)
                if page >= total_pages - 1:
                    break
                if max_pages is not None:
                    if page >= max_pages:
                        break
                page += 1
                try:
                    consultations_on_page = Consultation.from_list(feedback_info_str)
                    consultations.extend(consultations_on_page)
                    if stream_out_folder is not None:
                        save_to_json(
                            consultations=consultations_on_page,
                            output_folder=stream_out_folder,
                            filename=os.path.join("page" + str(page - 1) + ".json"),
                        )
                except JSONWizardError as exc:
                    logger.error(
                        f"Data {feedback_info_str} did not conform to data model (Consultation). {exc}"
                    )
    return consultations


def save_to_json(
    consultations: List[Consultation],
    output_folder: str | os.PathLike,
    filename: str | os.PathLike,
):
    """Save consultation data to JSON

    Args:
        consultations: Consultation dataclass object (probably created with eu_consultation_scrape.scrape.async_scrape)
        output_folder: folder to save JSON file to as "consultation_data.json"
    """
    json_output_path = os.path.join(output_folder, filename)
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    logger.info(f"Saving data to {json_output_path}")
    srsly.write_json(
        json_output_path, [instance.to_dict() for instance in consultations]
    )


def read_consultations_from_json(filepath: str | os.PathLike) -> List[Consultation]:
    """Save consultation data to JSON

    Args:
        filepath: path JSON of scraped consultations
    """
    scraped_json = srsly.read_json(filepath)
    consultations = Consultation.from_list(scraped_json)
    return consultations


def scrape(
    topic_list: list,
    output_folder: str | os.PathLike,
    filename: str | os.PathLike,
    max_pages: int | None = None,
    max_feedback: int | None = None,
) -> List[Consultation]:
    """Scrape consultation data from backend API of EU website

    Scrapes data from https://ec.europa.eu/info/law/better-regulation

    Args:
        topic_list: list of topics (as defined by the EU) to scrape. See eu_consultation_scraper.utils_scraping.TOPICS for the complete list of available topics.
        max_pages: set limit on number of pages to scrape. defaults to None (all pages)
        max_feedback: set limit on maximum of feedback to gather per consultation. defaults to None (no limit)
        output_folder: path to folder to stream out entire scraped data on all consultation, as well as JSON per scraped page in subfolder /pages.
    Returns:
        A list of Consultation dataclass objects. Can be further processed with download_consultation_files() and extract_text_from_attachments()
    """
    consultation_data = asyncio.run(
        async_scrape(
            topic_list=topic_list,
            max_pages=max_pages,
            max_feedback=max_feedback,
            stream_out_folder=os.path.join(output_folder, "pages"),
        )
    )
    save_to_json(consultation_data, output_folder, filename)
    return consultation_data
