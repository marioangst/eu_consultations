import shutil
import pathlib
import os


from eu_consultations.scrape import scrape, read_initiatives_from_json, scrape_topics_text
from eu_consultations.extract_filetext import (
    download_consultation_files,
    extract_text_from_attachments,
)
from eu_consultations.consultation_data import Initiative

OUTPUT_FILENAME = "consultation_data.json"


def test_scraping_creates_output_file(test_output_dir):
    scrape(
        topic_list=["DIGITAL"],
        output_folder=test_output_dir,
        filename=OUTPUT_FILENAME,
        max_pages=1,
    )
    # list all files
    out = pathlib.Path(test_output_dir)
    file_list = [str(item.name) for item in list(out.rglob("*")) if item.is_file()]
    shutil.rmtree(test_output_dir)
    assert OUTPUT_FILENAME in file_list


def test_scraped_data_conforms_to_dataclass_topic_query(test_output_dir):
    initiatives = scrape(
        topic_list=["DIGITAL"],
        output_folder=test_output_dir,
        filename=OUTPUT_FILENAME,
        max_pages=1,
        max_feedback=50,
    )
    stored_consultations = read_initiatives_from_json(
        os.path.join(test_output_dir, OUTPUT_FILENAME)
    )
    shutil.rmtree(test_output_dir)
    assert all([isinstance(item, Initiative) for item in initiatives])
    assert all([isinstance(item, Initiative) for item in stored_consultations])

def test_scraped_data_conforms_to_dataclass_text_query(test_output_dir):
    initiatives = scrape(
        text_list=["cloud","parrot"],
        output_folder=test_output_dir,
        filename=OUTPUT_FILENAME,
        max_pages=1,
        max_feedback=50,
    )
    stored_consultations = read_initiatives_from_json(
        os.path.join(test_output_dir, OUTPUT_FILENAME)
    )
    shutil.rmtree(test_output_dir)
    assert all([isinstance(item, Initiative) for item in initiatives])
    assert all([isinstance(item, Initiative) for item in stored_consultations])

def test_scraped_data_conforms_to_dataclass_topic_and_text_query(test_output_dir):
    initiatives = scrape(
        text_list=["cloud","parrot"],
        topic_list=["DIGITAL"],
        output_folder=test_output_dir,
        filename=OUTPUT_FILENAME,
        max_pages=1,
        max_feedback=50,
    )
    stored_consultations = read_initiatives_from_json(
        os.path.join(test_output_dir, OUTPUT_FILENAME)
    )
    shutil.rmtree(test_output_dir)
    assert all([isinstance(item, Initiative) for item in initiatives])
    assert all([isinstance(item, Initiative) for item in stored_consultations])

def test_full_pipeline_runs(test_output_dir):
    scrape_folder = test_output_dir
    # get minimal consultation data --------
    initiatives_data = scrape_topics_text(
        topic_list=["DIGITAL"],
        text_list = ["cloud"],
        max_pages=1,
        max_feedback=5,
    )
    # download files and add download path to data --------
    output_folder = os.path.join(scrape_folder, "files")
    data_with_downloads = download_consultation_files(
        initiatives_data=initiatives_data, output_folder=output_folder
    )
    data_with_extracted_text = extract_text_from_attachments(
        initiatives_data_with_attachments=data_with_downloads,
        stream_out_folder=output_folder,
    )
    # capture consultation ids
    consultation_ids = [c.id for c in initiatives_data]
    after_download_consultation_ids = [c.id for c in data_with_downloads]
    after_extraction_consultation_ids = [c.id for c in data_with_extracted_text]
    # remove output folder
    shutil.rmtree(test_output_dir)
    # basic data integrity tests
    assert (
        set(consultation_ids)
        == set(after_download_consultation_ids)
        == set(after_extraction_consultation_ids)
    )
    assert all([isinstance(item, Initiative) for item in data_with_downloads])
    assert all([isinstance(item, Initiative) for item in data_with_extracted_text])
