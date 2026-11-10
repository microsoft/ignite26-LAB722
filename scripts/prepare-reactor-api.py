"""Prepare only the explicitly authorized local allocation's dedicated API.

Policy metadata arrives on stdin, never in arguments, files or output.
Existing exact owned registrations are reconciled; uncertain POSTs are not retried.
"""
import argparse
import json
import sys
import time

import requests
from azure.identity import AzureCliCredential


class GraphError(RuntimeError):
    def __init__(self, status, code):
        self.status = status
        super().__init__(f"Graph HTTP {status}: {code}. Inspect the owned registration before retrying.")


class Graph:
    def __init__(self, credential):
        self.credential = credential

    def call(self, method, path, **kwargs):
        token = self.credential.get_token("https://graph.microsoft.com/.default").token
        try:
            response = requests.request(
                method, "https://graph.microsoft.com/v1.0/" + path,
                headers={"Authorization": "Bearer " + token}, timeout=60, **kwargs,
            )
        except requests.RequestException:
            raise RuntimeError(
                "Graph transport outcome is uncertain. Inspect the exact owned registration; "
                "no automatic retry or new creation was performed."
            ) from None
        if not response.ok:
            code = response.json().get("error", {}).get("code", "request_failed")
            raise GraphError(response.status_code, code)
        return response.json() if response.content else {}


def prepare(graph, subscription, resource_group, reference, sleep=time.sleep):
    name = f"LAB722 {resource_group} reactor execution API"
    owner = f"LAB722 local reactor: {subscription}/{resource_group}"
    matches = graph.call("GET", "applications", params={
        "$filter": "displayName eq '" + name.replace("'", "''") + "'",
        "$select": "id,appId,notes,signInAudience,identifierUris,api",
    })
    if matches.get("@odata.nextLink"):
        raise RuntimeError("API lookup is paginated; inspect it before choosing or creating a registration.")
    apps = matches["value"]
    if len(apps) > 1:
        raise RuntimeError("Multiple matching API registrations; no registration was chosen or created.")
    if apps:
        app = apps[0]
        if (app.get("notes") != owner or app.get("signInAudience") != "AzureADMyOrg"
                or app.get("api", {}).get("requestedAccessTokenVersion") != 1):
            raise RuntimeError("Matching application is not this allocation's approved v1 API; no change made.")
    else:
        body = {
            "displayName": name, "notes": owner, "signInAudience": "AzureADMyOrg",
            "api": {"requestedAccessTokenVersion": 1},
        }
        if reference:
            body["serviceManagementReference"] = reference
        app = graph.call("POST", "applications", json=body)
    audience = "api://" + app["appId"]
    uris = app.get("identifierUris", [])
    if uris and uris != [audience]:
        raise RuntimeError("Owned API has unexpected identifier URIs; no shared URI was replaced.")
    if not uris:
        graph.call("PATCH", "applications/" + app["id"], json={"identifierUris": [audience]})
    verified = graph.call("GET", "applications/" + app["id"], params={
        "$select": "id,appId,notes,identifierUris,signInAudience,api",
    })
    if (verified.get("notes") != owner or verified.get("identifierUris") != [audience]
            or verified.get("signInAudience") != "AzureADMyOrg"
            or verified.get("api", {}).get("requestedAccessTokenVersion") != 1):
        raise RuntimeError("Dedicated API read-back failed; do not proceed.")
    principals = graph.call("GET", "servicePrincipals", params={
        "$filter": f"appId eq '{app['appId']}'", "$select": "id,appId,appRoleAssignmentRequired",
    })
    if principals.get("@odata.nextLink") or len(principals["value"]) > 1:
        raise RuntimeError("Ambiguous API service principal; no creation performed.")
    if principals["value"]:
        principal = principals["value"][0]
    else:
        try:
            principal = graph.call("POST", "servicePrincipals", json={"appId": app["appId"]})
        except GraphError as error:
            if error.status != 404:
                raise
            sleep(15)
            principal = graph.call("POST", "servicePrincipals", json={"appId": app["appId"]})
    principal = graph.call("GET", "servicePrincipals/" + principal["id"], params={
        "$select": "id,appId,appRoleAssignmentRequired",
    })
    if principal.get("appId") != app["appId"] or principal.get("appRoleAssignmentRequired") is not False:
        raise RuntimeError("API service-principal ACL policy differs; no tenant policy was overridden.")
    return {"application_object_id": app["id"], "application_client_id": app["appId"],
            "service_principal_id": principal["id"], "audience": audience}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--resource-group", required=True)
    args = parser.parse_args()
    private = json.load(sys.stdin)
    with AzureCliCredential() as credential:
        result = prepare(Graph(credential), args.subscription, args.resource_group,
                         private.pop("service_management_reference", ""))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
