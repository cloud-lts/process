"""yolo."""

import json
from os import path
import subprocess
from typing import Any
import requests


def fetch_cves() -> list[dict[str, Any]]:
  """Fetches CVEs from NVD."""
  url = "https://services.nvd.nist.gov/rest/json/cves/2.0?lastModStartDate=2024-05-01T00:00:00&resultsPerPage=200&sourceIdentifier=416baaa9-dc9f-4396-8d5f-8c081fb06d67&lastModEndDate=2024-07-16T00:00:00"
  response = requests.get(url)
  if response.status_code != 200:
    print("Failed to fetch CVEs")
    return []
  results = json.loads(response.text)
  return [vuln["cve"] for vuln in results["vulnerabilities"]]


def evaluate_cve(cve: dict[str, Any], compiled_files: set[str]) -> bool:
  """Evaluates a CVE."""
  for ref in cve["references"]:
    if ref["url"].startswith("https://git.kernel.org/stable/c/"):
      commit = ref["url"].split("/")[-1].strip()
      # TODO(melotti): use a real library to do git things
      response = subprocess.run(
          ["git", "show", "--pretty=", "--name-only", commit],
          cwd="/usr/local/google/home/melotti/cloud-lts/linux",
          stdout=subprocess.PIPE,
          stderr=subprocess.DEVNULL,
          check=False,
      )
      if response.returncode != 0:
        continue
      affected_files = [
          line.decode("utf-8").strip() for line in response.stdout.splitlines()
      ]
      # print(f"Affected files: {affected_files}")
      return any((f in compiled_files) for f in affected_files)
  # print(f"No git commit found for {cve['id']}")
  return False


def main():
  with open("compiled_files.txt", "r") as f:
    compiled_files = f.readlines()
  compiled_files = set([path.normpath(f.strip()) for f in compiled_files])

  cves = fetch_cves()
  count = 0
  for cve in cves:
    print(f"Processing CVE: {cve['id']}")
    if evaluate_cve(cve, compiled_files):
      print(cve["id"])
      count += 1
  print(f"We care about {count} CVEs")

if __name__ == "__main__":
  main()
