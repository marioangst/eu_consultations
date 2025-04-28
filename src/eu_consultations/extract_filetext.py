import os
from typing import List

import httpx
from docling.document_converter import DocumentConverter
import srsly
from loguru import logger
from tqdm import tqdm

from eu_consultations.consultation_data import Initiative, DoclingDump
from eu_consultations.scrape import save_to_json


def download_file(url, filepath: str | os.PathLike) -> None | str | os.PathLike:
    """download file from url and return filepath of download location

    Args:
        url: url to download
        filepath: download filepath
    Returns:
        String with filepath to download location or None
    """
    try:
        r = httpx.get(url, timeout=None)
        with open(filepath, "wb") as f:
            f.write(r.content)
        logger.info(f"Downloaded {url}")
        return filepath
    except httpx.HTTPError as exc:
        logger.error(f"Could not download {exc.request.url} - {exc}.")


def download_consultation_files(
    initiatives_data: List[Initiative], output_folder: str | os.PathLike
) -> List[Initiative]:
    """download all files referenced in consultation data and return data with path to files appended

    Args:
        initiatives_data: List of Initiative dataclass objects
        output_folder: Path to folder to store files in

    Returns:
        List of Initiative dataclass objects with downloaded_filepath attribute set on attachments
    """
    # process all pdfs in a scrape
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    for initiative in initiatives_data:
        if initiative.consultations is not None:
            for consultation in tqdm(initiative.consultations, desc="Consultations"):
                if consultation.feedback is not None:
                    for feedback in tqdm(consultation.feedback, desc="Feedback"):
                        if feedback:
                            for attachment in feedback.attachments:
                                downloaded_filepath = download_file(
                                    url=attachment.links,
                                    filepath=os.path.join(
                                        output_folder,
                                        f"{attachment.document_id}_{attachment.file_name}",
                                    ),
                                )
                                if downloaded_filepath is not None:
                                    attachment.downloaded_filepath = downloaded_filepath
    return initiatives_data


def extract_text_from_attachments(
    initiatives_data_with_attachments: List[Initiative],
    stream_out_folder: str | os.PathLike | None,
    converter: DocumentConverter = DocumentConverter(),
) -> List[Initiative]:
    """extract text from all files referenced in consultation data using docling and return data with text appended

    Args:
        initiatives_data_with_attachments: List of Initiative dataclass objects with references to downloaded files set (probably created with download_consultation_files)
        stream_out_folder: Path to folder to stream out extracted texts as lossless JSON in Docling format per document (in subfolder "docling") and per consultation (in subfolder "consultation"). Defaults to none (no streaming out).
        converter: supply non-default DocumentConverter from docling

    Returns:
        List of Consultation dataclass objects with extracted text and docling json set on attachments
    """
    for initiative in initiatives_data_with_attachments:
        if initiative.consultations is not None:
            for consultation in tqdm(initiative.consultations, desc="Consultations"):
                if consultation.feedback is not None:
                    for feedback in tqdm(
                        consultation.feedback,
                        desc=f"Feedback for consultation {consultation.id} in inititative {initiative.short_title}",
                    ):
                        if feedback.attachments is not None:
                            for attachment in feedback.attachments:
                                if attachment.downloaded_filepath is not None:
                                    try:
                                        logger.info(
                                            f"Extracting {attachment.downloaded_filepath}"
                                        )
                                        result = converter.convert(
                                            attachment.downloaded_filepath
                                        )
                                        attachment.extracted_text = (
                                            result.document.export_to_text()
                                        )
                                        docling_dict = result.document.export_to_dict()
                                        docling_dump = DoclingDump.from_dict(
                                            docling_dict
                                        )
                                        attachment.docling_json = docling_dump
                                        if stream_out_folder is not None:
                                            docling_out_folder = os.path.join(
                                                stream_out_folder, "docling"
                                            )
                                            if not os.path.exists(docling_out_folder):
                                                os.makedirs(docling_out_folder)
                                            srsly.write_json(
                                                os.path.join(
                                                    docling_out_folder,
                                                    f"{str(attachment.document_id)}.json",
                                                ),
                                                docling_dict,
                                            )
                                    except Exception as e:
                                        logger.error(
                                            f"Could not extract {attachment.downloaded_filepath}: {e}"
                                        )
                    if stream_out_folder is not None:
                        save_to_json(
                            initiatives=[initiative],
                            output_folder=os.path.join(
                                stream_out_folder, "consultations"
                            ),
                            filename=f"{str(initiative.id)}.json",
                        )
    return initiatives_data_with_attachments
