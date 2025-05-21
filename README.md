# eu-consultations: A Python package for scraping textual data from EU public consultations

![PyPI - Python Version](https://img.shields.io/pypi/pyversions/eu-consultations)
![PyPI](https://img.shields.io/pypi/v/eu-consultations?label=pypi%20package)
![PyPI - Downloads](https://img.shields.io/pypi/dm/eu-consultations)

`eu-consultations` allows to scrape textual data from EU public consultation from https://ec.europa.eu/info/law/better-regulation. It's aim is to facilitate academic analysis of how the public participates in EU public consultations. In EU public consultations, the broader public of the EU is asked to supply input to proposed regulations.

The package has three main functions:

- Scrape metadata on feedback by the public to EU consultations by topic and/ or text search (in title and description of consultations) through accessing the API supplying the frontend to https://ec.europa.eu/info/law/better-regulation.
- Download files (e.g. .pdf and .docx) attached to feedback
- Extract text from files using [docling](https://github.com/docling-project/docling)

Downloaded data is validated and stored as JSON.

`eu-consultations`is partially based on https://github.com/desrist/AskThePublic.

## Installation

> ⚠️ `eu-consultations` requires **Python 3.12** or higher.

eu-consultations is available through PyPI:

```bash
pip install eu-consultations
```

## How to use `eu-consultations`

The following describes the typical pipeline for using `eu-consultations`:

### 1) Get consultation data

Here we will scrape data on consultations with the text "cloud" and "parrot" for the topic "DIGITAL". To get an overview over all possible topics, use:

```python
from eu_consultations.scrape import show_available_topics

show_available_topics()
```

Now let's scrape all metadata on feedback to consultations on the the topic "DIGITAL" (Digital economy and society), where the search terms "cloud" or "parrot" appear.

```python
from eu_consultations.scrape import scrape

initiatives_data = scrape(
    topic_list=["DIGITAL"],
    text_list=["cloud","parrot"],
    max_pages=None, # restrict number of frontend pages to crawl
    max_feedback = None, # set a maximum number of feedback to gather
    output_folder=<my-folder>,
    filename="<my-filename>.json")
```

This:
- serializes all data to <my-filename>.json in <my-folder>
- returns a list of `eu_consultations.consultation_data.Initiative` dataclass objects, which store feedback data per consultation

### 2) Download files attached to consultation feedback

Using our previous initial scrape, we can now download all attached files to feedback if we want to:

```python
from eu_consultations.extract_filetext import download_consultation_files

data_with_downloads = download_consultation_files(
    initiatives_data = initiatives_data,
    output_folder=<my-folder>)
```

This:
- downloads all attached files to <my-folder>/files
- returns a list of `eu_consultations.consultation_data.Initiative` dataclass objects with file locations attached

### 3) Extract texts

A lot of feedback to consultations already contains text on the opinions of the consulted available through step 1), but much of it is also contained in attached document. Let's extract the text and attach to our data:

```python
from eu_consultations.extract_filetext import extract_text_from_attachments

data_with_extracted_text = extract_text_from_attachments(
    initiatives_data_with_attachments = data_with_downloads, #created in step 2)
    stream_out_folder = <my-folder>/files #let's stream out to the same location as files
)
```

This:
- extracts text from all files referenced in `data_with_downloads`
- stores extracted text in lossless Docling JSON format per document at the folder set by stream_out_folder in a sub-directory `docling/` and per consultation at a sub-directory `consultations/`
- returns a list of `eu_consultations.consultation_data.Initiative` dataclass objects with text and docling JSON attached.

We can save the object, but be aware, it might be quite large:

```python
from eu_consultations.scrape import save_to_json

save_to_json(data_with_extracted_text, 
    <my-folder>, 
    filename="initiatives_with_extracted.json")
```

### Load serialized consultation data

If you have exported output from any of the above steps using `eu_consultations.scrape.save_to_json`, you can re-import into a list of `eu_consultations.consultation_data.Initiative` objects with `eu_consultations.scrape.read_initiatives_from_json`.

## Development

The package is developed using uv. Run tests (using pytest) with:

```bash
uv run pytest --capture no
```

The `--capture no` setting will show loguru log output. It is not necessary.

Some tests need a working internet connection and scrape small amounts of data from https://ec.europa.eu/info/law/better-regulation.