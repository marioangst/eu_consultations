import asyncio
from aiohttp.client_exceptions import ClientOSError
from bson import ObjectId
from loguru import logger
import httpx

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

BASE_URL = "https://ec.europa.eu/info/law/better-regulation"

API_PATH_INITIATIVES = "/brpapi/searchInitiatives?"
API_PATH_PUBLICATIONS = "/brpapi/groupInitiatives/"
API_PATH_FEEDBACK = f"/api/allFeedback?publicationId={{}}&keywords=&language=EN&page={{}}&size={INITIATIVES_PAGE_SIZE}&sort=dateFeedback,DESC"


def convert_objectid_to_str(data):
    if isinstance(data, list):
        return [convert_objectid_to_str(item) for item in data]
    elif isinstance(data, dict):
        return {key: convert_objectid_to_str(value) for key, value in data.items()}
    elif isinstance(data, ObjectId):
        return str(data)
    else:
        return data


# scraping data by initiatives topics.
async def fetch_data(session, url, params=None, semaphore=None, timeout=10):
    async with semaphore:
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"Error: {response.status} for URL: {url}")
                    return "no data"
        except asyncio.TimeoutError:
            logger.error(f"TimeoutError for URL: {url}")
            return "no data"
        except ClientOSError:
            logger.error(f"ClientOSError for URL: {url}")
            return "no data"


def get_total_pages_initiatives(topic=None, size=INITIATIVES_PAGE_SIZE) -> int:
    if topic is None:
        r = httpx.get(
            BASE_URL + API_PATH_INITIATIVES, params={"size": size}, timeout=None
        )
    else:
        r = httpx.get(
            BASE_URL + API_PATH_INITIATIVES,
            params={"topic": topic, "size": size},
            timeout=None,
        )
    total_pages = r.json()["page"]["totalPages"]
    return total_pages


# Pipeline 1: get all ids of initiatives for topic
async def get_initiatives_ids(session, topic, size, language, page, semaphore) -> list:
    url = BASE_URL + API_PATH_INITIATIVES
    params = {"topic": topic, "size": size, "language": language, "page": page}
    data = await fetch_data(session, url, params, semaphore)
    if data in ["no data", None]:
        return []

    initiatives_data = data.get("_embedded", {}).get("initiativeResultDtoes", [])
    id_list = [int(item.get("id")) for item in initiatives_data]
    return id_list


# Pipeline 2: get publication id
async def get_publication_id(session, id_list, semaphore, max_feedback: int | None):
    pubid = []

    tasks = []
    for id in id_list:
        url = BASE_URL + API_PATH_PUBLICATIONS + f"{id}"
        tasks.append(fetch_data(session, url, semaphore=semaphore))

    responses = await asyncio.gather(*tasks)
    for id, data in zip(id_list, responses):
        if not isinstance(data, dict):
            continue
        short_title = data.get("shortTitle")
        publications_data = data.get("publications", [])
        publication_ids = []
        frontendstage = []
        totalFeedback = []
        for item in publications_data:
            publi_id = item.get("id")
            total_Feedback = item.get("totalFeedback")
            frontEndStage = item.get("frontEndStage")
            # threshold check here
            if total_Feedback == 0:
                logger.info(
                    f"item skipped due to zero feedback: initiative id {id}, publication id {publi_id} {frontEndStage} "
                )
                continue
            if max_feedback is not None:
                if total_Feedback > max_feedback:
                    logger.warning(
                        f"item skipped due to feedback > {max_feedback} setting: initiative id {id}, publication id {publi_id} {frontEndStage})"
                    )
                    continue
            publication_ids.append(publi_id)
            frontendstage.append(frontEndStage)
            totalFeedback.append(total_Feedback)
        if publication_ids:  # only append if there are valid publication IDs
            pubid.append(
                {
                    "id": id,
                    "shortTitle": short_title,
                    "publicationId": publication_ids,
                    "frontEndStage": frontendstage,
                    "totalFeedback": totalFeedback,
                }
            )
        logger.info(f"Initiative {id} done")

    return pubid


# Pipeline 3: Get feedback information
async def get_feedback_info(
    session, pubid, topic, semaphore, limit_feedback: int | None = None
):
    feedback_info = []

    tasks = []
    for item in pubid:
        id = item["id"]
        shortTitle = item["shortTitle"]
        publicationId = item["publicationId"]
        frontendstage = item["frontEndStage"]
        totalFeedback = item["totalFeedback"]
        for i, pub_id in enumerate(publicationId):
            tasks.append(
                fetch_feedback(
                    session,
                    id,
                    shortTitle,
                    topic,
                    pub_id,
                    frontendstage[i],
                    totalFeedback[i],
                    semaphore,
                )
            )

    feedback_results = await asyncio.gather(*tasks)
    feedback_info.extend(feedback_results)
    feedback_info = process_data(feedback_info)

    return feedback_info


async def fetch_feedback(
    session, id, shortTitle, topic, pub_id, frontendstage, totalFeedback, semaphore
):
    feedback_info_url = BASE_URL + API_PATH_FEEDBACK
    feedback_data = []
    page_number = 0
    while True:
        url = feedback_info_url.format(pub_id, page_number)
        data = await fetch_data(session, url, semaphore=semaphore)
        if data == "no data":
            new_dic = {
                "id": id,
                "shortTitle": shortTitle,
                "topic": TOPICS.get(topic, "no topic"),
                "publicationId": pub_id,
                "frontEndStage": frontendstage,
                "totalFeedback": totalFeedback,
                "feedback": "no data",
            }
            return new_dic
        elif data:
            feedback_embedded = data.get("_embedded", {}).get("feedback", [])
            if not feedback_embedded:
                new_dic = {
                    "id": id,
                    "shortTitle": shortTitle,
                    "topic": TOPICS.get(topic, "no topic"),
                    "publicationId": pub_id,
                    "frontEndStage": frontendstage,
                    "totalFeedback": totalFeedback,
                    "feedback": "no data",
                }
                return new_dic

            # Process attachments within each feedback
            for feedback in feedback_embedded:
                if "attachments" in feedback:
                    for attachment in feedback["attachments"]:
                        attachment["links"] = (
                            f"https://ec.europa.eu/info/law/better-regulation/api/download/{attachment['documentId']}"
                        )
                        # Keep only id, fileName, documentId and links
                        attachment = {
                            "id": attachment.get("id"),
                            "fileName": attachment.get("fileName"),
                            "documentId": attachment.get("documentId"),
                            "links": attachment["links"],
                        }
                feedback_data.append(feedback)

            total_page = data.get("page", {}).get("totalPages", 0)
            if page_number >= total_page - 1:
                break
            page_number += 1
        else:
            break

    new_dic = {
        "id": id,
        "shortTitle": shortTitle,
        "topic": TOPICS.get(topic, "no topic"),
        "publicationId": pub_id,
        "frontEndStage": frontendstage,
        "totalFeedback": totalFeedback,
        "feedback": feedback_data,
    }
    return new_dic


# process data, delete unnecessary information of data
def process_data(feedback_info):
    processed_feedback_info = []

    for item in feedback_info:
        if item["feedback"] != "no data":
            feedback_data = item["feedback"]
            for feedback in feedback_data:
                # Remove _links field within each feedback
                if "_links" in feedback:
                    del feedback["_links"]

                # Process attachments field
                if "attachments" in feedback:
                    attachments = feedback["attachments"]
                    for attachment in attachments:
                        attachment_id = attachment.get("id")
                        file_name = attachment.get("fileName")
                        document_id = attachment.get("documentId")
                        attachment["id"] = attachment_id
                        attachment["fileName"] = file_name
                        attachment["documentId"] = document_id
                        attachment["links"] = (
                            f"https://ec.europa.eu/info/law/better-regulation/api/download/{document_id}"
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

                # Replace the original attachments with the processed ones
                feedback["attachments"] = attachments

            # Replace the original feedback with the processed feedback
            item["feedback"] = feedback_data

        processed_feedback_info.append(item)
    return processed_feedback_info
