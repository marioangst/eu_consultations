from typing import List

import httpx
from tqdm import tqdm
from loguru import logger

from eu_consultations.consultation_data import Initiative, Consultation, Feedback

TOPICS = {
    "AGRI": "Agriculture and rural development",
    "FINANCE": "Banking and financial services",
    "BORDERS": "Borders and security",
    "BUDGET": "Budget",
    "BUSINESS": "Business and industry",
    "CLIMA": "Climate action",
    "COMP": "Competition",
    "CONSUM": "Consumers",
    "CULT": "Culture and media",
    "CUSTOMS": "Customs",
    "DIGITAL": "Digital economy and society",
    "ECFIN": "Economy, finance and the euro",
    "EAC": "Education and training",
    "EMPL": "Employment and social affairs",
    "ENER": "Energy",
    "ENV": "Environment",
    "ENLARG": "EU enlargement",
    "NEIGHBOUR": "European neighbourhood policy",
    "FOOD": "Food safety",
    "FOREIGN": "Foreign affairs and security policy",
    "FRAUD": "Fraud prevention",
    "HOME": "Home affairs",
    "HUMAN": "Humanitarian aid and civil protection",
    "INST": "Institutional affairs",
    "INTDEV": "International cooperation and development",
    "JUST": "Justice and fundamental rights",
    "MARE": "Maritime affairs and fisheries",
    "ASYL": "Migration and asylum",
    "HEALTH": "Public health",
    "REGIO": "Regional policy",
    "RESEARCH": "Research and innovation",
    "SINGMARK": "Single market",
    "SPORT": "Sport",
    "STAT": "Statistics",
    "TAX": "Taxation",
    "TRADE": "Trade",
    "TRANSPORT": "Transport",
    "YOUTH": "Youth",
}

INITIATIVES_PAGE_SIZE = 10
LANGUAGE_SETTING = "EN"

BASE_URL = "https://ec.europa.eu/info/law/better-regulation"

API_PATH_INITIATIVES = "/brpapi/searchInitiatives?"
API_PATH_PUBLICATIONS = "/brpapi/groupInitiatives/"
FEEDBACK_URL = "/api/allFeedback"


# getting consultation ids


def get_total_pages_initiatives(topic: str | None, text: str | None) -> int:
    url = BASE_URL + API_PATH_INITIATIVES
    if topic is None:
        params = {"page": 0, "size": INITIATIVES_PAGE_SIZE, "text": text, "language": LANGUAGE_SETTING}
    if text is None:
        params = {"page": 0, "size": INITIATIVES_PAGE_SIZE, "topic": topic}
    if text is not None and topic is not None:
        params = {"topic": topic, "page": 0, "size": INITIATIVES_PAGE_SIZE, "text": text, "language": LANGUAGE_SETTING}
    r = httpx.get(url, params=params, timeout=None)
    total_pages = r.json()["page"]["totalPages"]
    return total_pages


def get_ids_for_page_initiatives(topic: str | None, text: str | None, page: int) -> List[int]:
    url = BASE_URL + API_PATH_INITIATIVES
    if topic is None:
        params = {"page": page, "size": INITIATIVES_PAGE_SIZE, "text": text, "language": LANGUAGE_SETTING}
    if text is None:
        params = {"page": page, "size": INITIATIVES_PAGE_SIZE, "topic": topic}
    if text is not None and topic is not None:
        params = {"topic": topic, "page": page, "size": INITIATIVES_PAGE_SIZE, "text": text, "language": LANGUAGE_SETTING}
    r = httpx.get(url, params=params, timeout=None)
    initiatives = r.json()["_embedded"]["initiativeResultDtoes"]
    ids = [int(initiative["id"]) for initiative in initiatives]
    return ids


def get_ids_for_query(topic: str | None, text: str | None, max_pages: int | None = None) -> List[int]:
    total_pages_found = get_total_pages_initiatives(topic, text)
    if max_pages is not None:
        total_pages_to_scrape = max_pages
        logger.warning(f"scrapping only {max_pages} page due to max_pages setting")
    else:
        total_pages_to_scrape = total_pages_found
    ids = []
    if total_pages_found > 0:
        for page in tqdm(range(0, total_pages_to_scrape), desc="Gathering page ids"):
            page_ids = get_ids_for_page_initiatives(topic = topic, text = text, page = page)
            ids.extend(page_ids)
    return ids



# get data on initiatives for specific initiative id


def get_initiative_data(id: int) -> Initiative:
    # get all publications under id
    url = BASE_URL + API_PATH_PUBLICATIONS + str(id)
    r = httpx.get(url)
    data = r.json()
    consultations_list = Consultation.from_list(data["publications"])
    initiative = Initiative.from_dict(
        {i: data[i] for i in data if i not in "publications"}
    )
    initiative.consultations = consultations_list
    return initiative


# getting publications with potential feedbacks for initiatives


def get_total_pages_feedback(consultation: Consultation) -> int:
    url = BASE_URL + "/api/allFeedback"
    params = {
        "publicationId": consultation.id,
        "size": INITIATIVES_PAGE_SIZE,
        "page": 0,
    }
    r = httpx.get(url, params=params)
    total_pages = r.json()["page"]["totalPages"]
    return total_pages


def get_feedback_for_page(consultation, page) -> List[Feedback]:
    url = BASE_URL + "/api/allFeedback"
    params = {
        "publicationId": consultation.id,
        "size": INITIATIVES_PAGE_SIZE,
        "page": page,
    }
    r = httpx.get(url, params=params)
    # remove _links data
    feedback_data = r.json()["_embedded"]["feedback"]
    for feedback in feedback_data:
        if "_links" in feedback:
            del feedback["_links"]
            # Process attachments field
        if "attachments" in feedback:
            for attachment in feedback["attachments"]:
                attachment["links"] = (
                    f"https://ec.europa.eu/info/law/better-regulation/api/download/{attachment['documentId']}"
                )
                # Remove unwanted fields
                keys_to_remove = set(attachment.keys()) - {
                    "id",
                    "fileName",
                    "documentId",
                    "links",
                }
                for key in keys_to_remove:
                    del attachment[key]
    feedbacks = Feedback.from_list(feedback_data)
    return feedbacks


def get_feedback_for_consultation(
    consultation: Consultation, max_feedback: int | None = None
) -> List[Feedback] | None:
    if consultation.total_feedback == 0:
        return None
    if max_feedback is not None:
        if consultation.total_feedback > max_feedback:
            logger.warning(
                f"skipping consultation {consultation.id} because of max_feedback setting"
            )
            return None
    else:
        total_pages = get_total_pages_feedback(consultation=consultation)
        feedbacks = []
        for page in tqdm(
            range(0, total_pages),
            desc=f"Gathering feedback for consultation {consultation.id}",
        ):
            feedback_per_page = get_feedback_for_page(
                consultation=consultation, page=page
            )
            feedbacks.extend(feedback_per_page)
        return feedbacks


def scrape_query(
    topic: str | None,
    text: str | None,
    max_pages: int | None = None,
    max_feedback: int | None = None,
) -> List[Initiative]:
    initiative_ids = get_ids_for_query(topic = topic, text = text, max_pages=max_pages)
    initiatives = []
    for id in tqdm(initiative_ids, desc="Gathering initiative data"):
        initiative = get_initiative_data(id)
        initiatives.append(initiative)
    for initiative in tqdm(initiatives, desc="Processing initiatives"):
        for consultation in initiative.consultations:
            try:
                feedbacks = get_feedback_for_consultation(
                    consultation, max_feedback=max_feedback
                )
                consultation.feedback = feedbacks
            except Exception as e:
                logger.error(
                    f"Could not process consultation {consultation.id} initiative {initiative.id}: {e}"
                )
    return initiatives
