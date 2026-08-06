# -*- coding: utf-8 -*-
import json
import urllib.request
from pathlib import Path

tok = (
    Path(r"C:\Users\hysoo\projects\RoadLog\.launch\railway.token")
    .read_text(encoding="utf-8-sig")
    .strip()
    .splitlines()[0]
    .strip()
    .strip('"')
    .strip("'")
)
E = "367f2cc2-ac64-4daf-b04d-0d28f4ac97c7"
S = "ebf3faf1-2f14-425a-acad-9cc2c67fa633"
# RoadLog project - need project id
# from earlier memory E and S were RoadLog

q = """
query($input: DeploymentListInput!) {
  deployments(input: $input) {
    edges {
      node {
        id
        status
        createdAt
        meta
      }
    }
  }
}
"""
# try without projectId
body = json.dumps(
    {
        "query": """
        query {
          deployments(
            first: 8
            input: {
              environmentId: "%s"
              serviceId: "%s"
            }
          ) {
            edges { node { id status createdAt staticUrl } }
          }
        }
        """
        % (E, S)
    }
).encode()
req = urllib.request.Request(
    "https://backboard.railway.app/graphql/v2",
    data=body,
    headers={
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
    },
    method="POST",
)
print(urllib.request.urlopen(req, timeout=60).read().decode()[:2000])
