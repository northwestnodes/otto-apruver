#!/usr/bin/env python3
import os
import sys
import requests
import time
import json
from typing import List, Dict, Any



def load_approvable_states() -> set[str]:
    raw = os.getenv("CL_APPROVABLE_STATES")
    if not raw:
        print("[WARN] CL_APPROVABLE_STATES not set. Using default states.")
        return {
            "PENDING",
            "REQUIRES_ADMIN_APPROVAL",
            "VERSION_PENDING",
            "PROPOSED",
            "CANCELLED",
        }
    states = {s.strip().upper() for s in raw.split(",") if s.strip()}
    print(f"[INFO] Loaded APPROVABLE_STATES from env: {states}")
    return states



NODE_URL = os.getenv("CL_NODE_URL")
CL_EMAIL = os.getenv("CL_EMAIL")
CL_PASSWORD = os.getenv("CL_PASSWORD")
FEEDS_MANAGER_ID = os.getenv("CL_FEEDS_MANAGER_ID", "1")
INTERVAL = os.getenv("CL_INTERVAL", "300")
NETWORK = os.getenv("CL_NETWORK")
GRAPHQL_ENDPOINT = NODE_URL.rstrip("/") + "/query"
SESSIONS_ENDPOINT = NODE_URL.rstrip("/") + "/sessions"
SLACK_WEBHOOK_URL = os.getenv("CL_SLACK_WEBHOOK")
APPROVABLE_STATES = load_approvable_states()



session = requests.Session()



def die(msg: str, code: int = 1):
    print(f"[FATAL] {msg}", file=sys.stderr)
    sys.exit(code)



def log(msg: str):
    """
    Send a Slack message using an incoming webhook.
    """
    if not SLACK_WEBHOOK_URL:
        print(f"[WARN] SLACK_WEBHOOK_URL not set, message not sent: {msg}")
        return
    
    msg = f'[{NETWORK}] {msg}'
    payload = {"text": msg}

    try:
        resp = requests.post(
            SLACK_WEBHOOK_URL,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
    except Exception as e:
        print(f"[ERROR] Failed to send Slack message: {e}")
        return

    if resp.status_code not in (200, 204):
        print(f"[ERROR] Slack returned HTTP {resp.status_code}: {resp.text}")



def login():
    if not CL_EMAIL or not CL_PASSWORD:
        die("CL_EMAIL and CL_PASSWORD environment variables are required")
    print(f"[INFO] Logging into Chainlink node at {SESSIONS_ENDPOINT} ...")

    try:
        resp = session.post(SESSIONS_ENDPOINT, json={"email": CL_EMAIL, "password": CL_PASSWORD}, timeout=10, verify=False)
    except requests.RequestException as e:
        die(f"Error connecting to node while logging in: {e}")

    if resp.status_code != 200:
        die(f"Login failed, status={resp.status_code}, body={resp.text}")
    print("[INFO] Login successful, session cookie acquired.")



def logout():
    print("[INFO] Logging out of Chainlink node...")
    try:
        resp = session.delete(SESSIONS_ENDPOINT, timeout=10, verify=False)
    except Exception as e:
        print(f"[WARN] Logout request failed in a very on-brand Chainlink way: {e}")
        return
    
    if resp.status_code not in (200, 204):
        print(f"[WARN] Logout returned HTTP {resp.status_code}: {resp.text[:300]}")
    else:
        print("[INFO] Logout complete. Session closed.")



def gql(query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
    payload = {"query": query}
    if variables is not None:
        payload["variables"] = variables

    try:
        resp = session.post(GRAPHQL_ENDPOINT, json=payload, timeout=15)
    except requests.RequestException as e:
        die(f"GraphQL request failed: {e}")

    if resp.status_code != 200:
        die(f"GraphQL HTTP error {resp.status_code}: {resp.text}")

    data = resp.json()
    if "errors" in data:
        die(f"GraphQL errors: {data['errors']}")

    return data.get("data", {})



def fetch_job_proposals() -> list[dict]:
    """
    Fetch job proposals via the same GraphQL query the Operator UI uses:
    FetchFeedManagerWithProposals(id: ID!)

    Returns a flat list of JobProposal objects:
    [
      {
        "id": "...",
        "name": "...",
        "externalJobID": "...",
        "remoteUUID": "...",
        "status": "PENDING" | "APPROVED" | ...,
        "pendingUpdate": bool,
        "latestSpec": {
          "createdAt": "...",
          "version": int,
        },
        "__typename": "JobProposal",
      },
      ...
    ]
    """

    query = """
    query FetchFeedManagerWithProposals($id: ID!) {
      feedsManager(id: $id) {
        __typename
        ... on FeedsManager {
          id
          name
          jobProposals {
            id
            name
            externalJobID
            remoteUUID
            status
            pendingUpdate
            latestSpec {
              createdAt
              version
              __typename
            }
            __typename
          }
        }
        ... on NotFoundError {
          message
          code
        }
      }
    }
    """

    variables = {"id": str(FEEDS_MANAGER_ID)}
    print(f"[INFO] Fetching job proposals via GraphQL for feedsManager id={FEEDS_MANAGER_ID} ...")

    data = gql(query, variables)  # uses your existing gql() helper

    fm = data.get("feedsManager")
    if not fm:
        print("[WARN] No feedsManager in GraphQL response.")
        return []

    typename = fm.get("__typename")
    if typename != "FeedsManager":
        # Handle union error: NotFoundError, etc.
        msg = fm.get("message")
        code = fm.get("code")
        print(f"[ERROR] feedsManager query did not return FeedsManager. "
              f"__typename={typename}, code={code}, message={msg}")
        return []

    proposals = fm.get("jobProposals") or []
    print(f"[INFO] Retrieved {len(proposals)} job proposals from feedsManager {fm.get('id')!r} ({fm.get('name')!r}).")
    return proposals



def filter_approvable(proposals: list[dict]) -> list[dict]:
    ready = []
    for p in proposals:
        status = (p.get("status") or "").upper()
        if status in APPROVABLE_STATES:
            ready.append(p)

    print(f"[INFO] Found {len(ready)} proposals in approvable states: {sorted(APPROVABLE_STATES)}")

    if len(ready) > 0:
        log(f"[INFO] Found {len(ready)} proposals in approvable states: {sorted(APPROVABLE_STATES)}")

    return ready



def approve_job_proposal_spec(spec_id: str, force: bool = True) -> bool:
    mutation = """
    mutation ApproveJobProposalSpec($id: ID!, $force: Boolean) {
      approveJobProposalSpec(id: $id, force: $force) {
        __typename
        ... on ApproveJobProposalSpecSuccess {
          spec {
            id
            __typename
          }
          __typename
        }
        ... on NotFoundError {
          message
          __typename
        }
      }
    }
    """

    variables = {"id": str(spec_id), "force": force}
    print(f"[INFO] Approving job proposal spec id={spec_id} (force={force}) ...")

    data = gql(mutation, variables)
    result = data.get("approveJobProposalSpec")

    if not result:
        print(f"[ERROR] approveJobProposalSpec returned no data for spec id={spec_id}")
        log(f"[ERROR] approveJobProposalSpec returned no data for spec id={spec_id}")
        return False

    typename = result.get("__typename")
    if typename == "ApproveJobProposalSpecSuccess":
        spec = result.get("spec") or {}
        print(f"[INFO] Successfully approved spec id={spec.get('id')}")
        log(f"[INFO] Successfully approved spec id={spec.get('id')}")
        return True

    if typename == "NotFoundError":
        print(f"[ERROR] Spec not found while approving id={spec_id}: {result.get('message')}")
        log(f"[ERROR] Spec not found while approving id={spec_id}: {result.get('message')}")
        return False

    print(f"[ERROR] Unexpected response type from approveJobProposalSpec: {typename}")
    log(f"[ERROR] Unexpected response type from approveJobProposalSpec: {typename}")    
    return False



def main():
    print("[INFO] Chainlink auto-approver starting up.")

    login()

    proposals = fetch_job_proposals()
    if not proposals:
        print("[INFO] No proposals returned. Nothing to do.")
        logout()
        return

    approvable = filter_approvable(proposals)
    if not approvable:
        print("[INFO] No proposals in approvable states. Nothing to do.")
        logout()
        return

    failures = 0
    for p in approvable:
        pid = p.get("id")
        state = p.get("state")
        ext = p.get("externalJobID")
        name = p.get("name")

        print(
            f"[INFO] Processing proposal id={pid}, state={state}, "
            f"externalJobID={ext}, name={name}"
        )

        try:
            approve_job_proposal_spec(pid)
        except SystemExit:
            raise
        except Exception as e:
            failures += 1
            print(f"[ERROR] Failed to approve proposal id={pid}: {e}", file=sys.stderr)
            logout()

    print(f"[INFO] Done. Attempted {len(approvable)} approvals, failures={failures}, successes={len(approvable) - failures}.")

    if len(approvable) > 0:
        log(f"[INFO] Done. Attempted {len(approvable)} approvals, failures={failures}, successes={len(approvable) - failures}.")

    logout()



if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            print(f"[ERROR] main() exploded: {e}")

        print(f"[INFO] Sleeping {int(INTERVAL)} seconds ...")
        time.sleep(int(INTERVAL))
