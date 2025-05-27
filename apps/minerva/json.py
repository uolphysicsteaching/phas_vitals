# -*- coding: utf-8 -*-
"""Functions to work with the Azure blob store with the data from Minerva."""
# Python imports
import logging
import os
from json import loads as dumb_loads

# Django imports
from django.conf import settings

# external imports
# MS Azure imports
from azure.storage.blob import BlobServiceClient
from jsondatetime import loads as smart_loads

logger = logging.getLogger(__name__)

# Ensure we lose the http_proxy before accessing web-resources
if "http_proxy" in os.environ:
    del os.environ["http_proxy"]
if "https_proxy" in os.environ:
    del os.environ["https_proxy"]


def get_blob_service_client(sas_url=None):
    """Return a BlobServiceClient using the secret SAS settings."""
    if sas_url is None:
        sas_url = f"{settings.SAS_DATA['URL']}{settings.SAS_DATA['TOKEN']}"

    try:
        return BlobServiceClient(account_url=sas_url)
    except Exception as ex:
        logger.error(f"Unable to open BlobClient - error {ex}")


def get_container_client(container_name=None, blob_service_client=None):
    """Get a Blob container client, use django settings by default."""
    if blob_service_client is None:
        blob_service_client = get_blob_service_client()
    if container_name is None:
        container_name = settings.SAS_DATA["CONTAINER"]
    try:
        return blob_service_client.get_container_client(container_name)
    except Exception as ex:
        logger.error(f"Unable to open ContainerClient - error {ex}")


def get_blob_client(blob_name, container_name=None, blob_service_client=None):
    """Get a Blob container client, use django settings by default."""
    if blob_service_client is None:
        blob_service_client = get_blob_service_client()
    if container_name is None:
        container_name = settings.SAS_DATA["CONTAINER"]
    container_client = get_container_client(container_name=container_name, blob_service_client=blob_service_client)
    blobs = get_blob_list(container_client)
    if blob_name in blobs:
        blob_name = blobs[blob_name]["name"]
    try:
        return blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    except Exception as ex:
        logger.error(f"Unable to open ContainerClient - error {ex}")


def get_blob_list(container_client=None):
    """Build a dictionary of blobs in the store."""
    if container_client is None:
        container_client = get_container_client()
    blob_list = container_client.list_blobs()
    ret = {}
    for blob in blob_list:
        name_parts = blob.name.split("/")
        if name_parts[-1].endswith(".json") or name_parts[-1].endswith(".DataReady"):
            ret[name_parts[-1]] = blob
    return ret


def get_blob_by_name(name, smart_dates=True, raw=False):
    """Read a blob name and convert it to a json data structure."""
    container_client = get_container_client()
    blobs = get_blob_list(container_client)
    loads = smart_loads if smart_dates else dumb_loads
    return_data = []
    if name in blobs:
        blob = blobs[name]
        try:
            raw_data = container_client.download_blob(blob.name).read()
            if raw:
                return raw_data
            for line in raw_data.split(b"\r\n"):
                if line.strip() == b"" or line.strip().startswith(b"#"):  # blank lines and comments
                    continue
                data = loads(line)
                if "results" in data:
                    return_data.extend(data["results"])
                else:
                    logger.error("No results key in line of json data!")
        except Exception as ex:
            logger.error(f"Failed to download nlob {blob.name}  -error {ex}")
            return None
        return return_data
    logger.error(f"Blob {name} not in store!")
    return None
