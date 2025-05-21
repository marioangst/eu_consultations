import os
from typing import List

from loguru import logger
import srsly
from tqdm import tqdm

from eu_consultations.utils_scraping import (
    TOPICS,
    scrape_query,
    get_initiative_data,
    get_feedback_for_consultation,
)
from eu_consultations.consultation_data import Initiative


def show_available_topics():
    return TOPICS


def scrape_topics_text(
    topic_list: list | None,
    text_list: list | None,
    max_pages: int | None,
    max_feedback: int | None,
) -> List[Initiative]:
    """Scrape consultation data from backend API of EU website

    Scrapes data from https://ec.europa.eu/info/law/better-regulation

    Args:
        topic_list: list of topics to scrape
        text_list: list of text matches to scrape
        max_pages: set limit on number of pages to scrape.
        max_feedback: set limit on maximum of feedback to gather per consultation
    Returns:
        A list of Consultation dataclass object
    """
    logger.info("starting scraping")
    initiatives = []
    if topic_list is not None: 
        not_allowed_topics = [
            not_allowed for not_allowed in topic_list if not_allowed not in TOPICS.keys()
        ]
        if len(not_allowed_topics) > 0:
            logger.error(
                f"The topic(s) {' '.join(not_allowed_topics)} are not allowed topics. Topic must be one of {' '.join(TOPICS)}."
            )
            raise ValueError("topic list contains not allowed topics")
    if topic_list is not None and text_list is None:
        for topic in topic_list:
            logger.info(f"scraping topic {topic}")
            initiatives_topic = scrape_query(
                topic = topic, text = None, max_pages=max_pages, max_feedback=max_feedback
            )
            initiatives.extend(initiatives_topic)
    if topic_list is None and text_list is not None:
        for text in text_list:
            logger.info(f"scraping for text query {text}")
            initiatives_topic = scrape_query(
                topic = None, text = text, max_pages=max_pages, max_feedback=max_feedback
            )
            initiatives.extend(initiatives_topic)
    if topic_list is not None and text_list is not None:
        for topic in topic_list:
            for text in text_list:
                logger.info(f"scraping for text query {text} in topic {topic}")
                initiatives_topic = scrape_query(
                    topic = topic, text = text, max_pages=max_pages, max_feedback=max_feedback
                )
                initiatives.extend(initiatives_topic)
    return initiatives


def scrape_initiative(id: int) -> List[Initiative]:
    initiatives = [get_initiative_data(id)]
    for initiative in tqdm(initiatives, desc="Processing initiatives"):
        if initiative.consultations is not None:
            for consultation in initiative.consultations:
                try:
                    feedbacks = get_feedback_for_consultation(consultation)
                    consultation.feedback = feedbacks
                except Exception as e:
                    logger.error(
                        f"Could not process consultation {consultation.id} initiative {initiative.id}: {e}"
                    )
    return initiatives


def save_to_json(
    initiatives: List[Initiative],
    output_folder: str | os.PathLike,
    filename: str | os.PathLike,
):
    """Save consultation data to JSON

    Args:
        initiatives: Initiatives dataclass object
        output_folder: folder to save JSON file to
    """
    json_output_path = os.path.join(output_folder, filename)
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    logger.info(f"Saving data to {json_output_path}")
    srsly.write_json(json_output_path, [instance.to_dict() for instance in initiatives])


def read_initiatives_from_json(filepath: str | os.PathLike) -> List[Initiative]:
    """Read scraped data on JSON

    Args:
        filepath: path JSON of scraped initiatives
    """
    scraped_json = srsly.read_json(filepath)
    initiatives = Initiative.from_list(scraped_json)
    return initiatives


def scrape(
    output_folder: str | os.PathLike,
    filename: str | os.PathLike,
    topic_list: list | None = None,
    text_list: list | None = None,
    max_pages: int | None = None,
    max_feedback: int | None = None,
) -> List[Initiative]:
    """Scrape consultation data from backend API of EU website

    Scrapes data from https://ec.europa.eu/info/law/better-regulation

    Args:
        output_folder: path to folder to stream out entire scraped data on all consultation, as well as JSON per scraped page in subfolder /pages.
        filename: filename for json file with output.
        topic_list: list of topics (as defined by the EU) to scrape. See eu_consultations.utils_scraping.TOPICS for the complete list of available topics. Defaults to None (all topics).
        text_list: list of search queries (text) to look for in consultation titles and descriptions. Defaults to None (no search query)
        max_pages: set limit on number of pages to scrape. defaults to None (all pages)
        max_feedback: set limit on maximum of feedback to gather per consultation. defaults to None (no limit)
    Returns:
        A list of Initiative dataclass objects. Can be further processed with download_consultation_files() and extract_text_from_attachments()
    """
    initiatives_data = scrape_topics_text(
        topic_list=topic_list,
        text_list=text_list,
        max_pages=max_pages,
        max_feedback=max_feedback,
    )
    save_to_json(initiatives_data, output_folder, filename)
    return initiatives_data
