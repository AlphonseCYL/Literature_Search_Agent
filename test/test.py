from typing import Any, Optional
from elasticsearch import Elasticsearch, helpers

def main() -> None:
    client_kwargs: dict[str, Any] = {
        "request_timeout": 60,
        "basic_auth": ("elastic", "000000"),
        "api_key": "QjFhLXpaMEJHck9zd3ZCMDdEdVE6QWN2MGluZHcwbGRTSm9ORURoQ0tnUQ=="
        }
    client = Elasticsearch(
        hosts="http://127.0.0.1:9200",
        #basic_auth=client_kwargs["basic_auth"],
        api_key=client_kwargs["api_key"],
        request_timeout=client_kwargs["request_timeout"]
    )

    index_name = "test"
    mappings = {
        "properties": {
            "title": {
                "type": "text"
            },
            "author": {
                "type": "text"
            },
            "platform": {
                "type": "text"
            }
        }
    }

    mapping_response = client.indices.put_mapping(index=index_name, body=mappings)
    print(mapping_response)

    docs = [
        {"title": "Document 1", "author": "Author A", "platform": "Platform X"},
        {"title": "Document 2", "author": "Author B", "platform": "Platform Y"},
        {"title": "Document 3", "author": "Author C", "platform": "Platform Z"}
    ]
    bulk_response = helpers.bulk(client, docs, index=index_name)
    print(bulk_response)
if __name__ == "__main__":
    main()
