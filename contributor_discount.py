# The MIT License (MIT)
#
# Copyright (c) 2016 chickadee-tech
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import print_function

import json
import requests
import time
import datetime

import logging

import sys

MERGE = 1
COMMIT = 3
WIKI = 1
DUPLICATE_COMMIT = 0
COMMENT = 0.1
RELEASE = 100
PRERELEASE = 50

WEEK_MULTIPLIER = 3
MONTH_MULTIPLIER = 2
QUARTER_MULTIPLIER = 1

WEEK = datetime.timedelta(7)
MONTH = datetime.timedelta(30)
QUARTER = datetime.timedelta(90)

PERCENT_10 = 1
PERCENT_15 = 200
PERCENT_20 = 500

CKD_MULTIPLIER = 3

def parse_datetime(d):
  return datetime.datetime.strptime(d, "%Y-%m-%dT%H:%M:%SZ")

REPOS = ["betaflight/betaflight", "betaflight/betaflight-configurator", "ShikOfTheRa/scarab-osd", "cleanflight/cleanflight", "cleanflight/cleanflight-configurator", "iNavFlight/inav", "chickadee-tech/betaflight", "chickadee-tech/acro"]

def compute_discount(github, author):
  score = 0
  now = datetime.datetime.now()
  repos = {}
  for page in xrange(1,11):
    body = github.get("users/" + author + "/events/public?page=" + str(page))

    commits_code = False
    for event in body:
      t = event["type"]
      event_score = 0
      event_date = None
      if t in ["PushEvent", "PullRequestEvent"]:
        if event["repo"]["name"] in REPOS:
          commits_code = True
      elif t == "GollumEvent":
        if event["repo"]["name"] in REPOS:
          #print(json.dumps(event, sort_keys=True, indent=2, separators=(',', ': ')))
          #print(t, event["created_at"], event["repo"]["id"], event["repo"]["name"])
          was_edit = False
          for page in event["payload"]["pages"]:
            if page["action"] == "edited":
              was_edit = True
              break
          if was_edit:
            event_date = parse_datetime(event["created_at"])
            event_score = WIKI
      elif t in ["IssuesEvent", "IssueCommentEvent", "CommitCommentEvent", "PullRequestReviewCommentEvent"]:
        if event["repo"]["name"] in REPOS:
          #print(t, event["created_at"], event["repo"]["id"], event["repo"]["name"])
          event_date = parse_datetime(event["created_at"])
          event_score = COMMENT
      elif t in ["CreateEvent", "ForkEvent", "WatchEvent", "DeleteEvent"]:
        pass
      elif t == "ReleaseEvent":
        if event["repo"]["name"] in REPOS:
          #print(json.dumps(event["payload"], sort_keys=True, indent=2, separators=(',', ': ')))
          release = event["payload"]["release"]
          event_date = parse_datetime(release["created_at"])
          if release["prerelease"]:
            event_score = PRERELEASE
          else:
            event_score = RELEASE
      else:
        # print(t)
        # print(json.dumps(event, sort_keys=True, indent=2, separators=(',', ': ')))
        pass

      if event_date:
        event_age = now - event_date
        if event_age < WEEK:
          event_score *= WEEK_MULTIPLIER
        elif event_age < MONTH:
          event_score *= MONTH_MULTIPLIER
        elif event_age < QUARTER:
          event_score *= QUARTER_MULTIPLIER
        else:
          break
      if event["repo"]["name"].startswith("chickadee-tech/"):
        event_score *= CKD_MULTIPLIER
      if event_score > 0:
        if event["repo"]["name"] not in repos:
          repos[event["repo"]["name"]] = 0
        repos[event["repo"]["name"]] += event_score
      score += event_score

    if len(body) < 30:
      break

  if commits_code:
    commits = set()
    for repo in REPOS:
      commit_age = now - now
      page = 1
      potentially_more = True
      while commit_age < QUARTER and potentially_more:
        body = github.get("repos/" + repo + "/commits?per_page=100&page=" + str(page) + "&author=" + author)
        page += 1
        if len(body) < 100:
          potentially_more = False
        for commit in body:
          #print(json.dumps(commit, sort_keys=True, indent=2, separators=(',', ': ')))
          commit_sha = commit["sha"]
          commit_date = datetime.datetime.strptime(commit["commit"]["committer"]["date"], "%Y-%m-%dT%H:%M:%SZ")
          commit_age = now - commit_date
          num_parents = len(commit["parents"])
          #print(commit["commit"]["committer"]["date"], num_parents, now - commit_date)
          commit_score = 0
          if num_parents > 1:
            commit_score = MERGE
          elif commit_sha not in commits:
            commits.add(commit_sha)
            commit_score = COMMIT
          else:
            commit_score = DUPLICATE_COMMIT

          if repo.startswith("chickadee-tech"):
            commit_score *= CKD_MULTIPLIER

          if commit_age < WEEK:
            commit_score *= WEEK_MULTIPLIER
          elif commit_age < MONTH:
            commit_score *= MONTH_MULTIPLIER
          elif commit_age < QUARTER:
            commit_score *= QUARTER_MULTIPLIER
          else:
            break

          if commit_score > 0:
            if repo not in repos:
              repos[repo] = 0
            repos[repo] += commit_score
          score += commit_score

  repo_names = repos.keys()
  repo_names.sort(key=lambda x: repos[x], reverse=True)
  blurbs = []
  for repo in repo_names:
    blurbs.append("<a href=\"https://github.com/" + repo + "\">" + repo + "</a> (" + str(repos[repo]) + ")")
  if len(blurbs) > 1:
    thanks = "Thank you for your contributions to " + ", ".join(blurbs[:-1]) + " and " + blurbs[-1] + "!"
  else:
    thanks = "Thank you for your contributions to " + blurbs[0] + "!"

  discount_percentage = 0
  if score > PERCENT_20:
    discount_percentage = 20
  elif score > PERCENT_15:
    discount_percentage = 15
  elif score > PERCENT_10:
    discount_percentage = 10

  return (discount_percentage, score, thanks)

def get_discount_code(lemonstand_auth_token, author, discount_percentage, score):
  discount_code = "ACD-V1-" + author.upper() + "-" + str(score) + "-" + str(int(time.time()))
  discount = {
    "name": "Active Contributor Discount for " + author,
    "coupon_codes": discount_code,
    "subtotal_discount": str(discount_percentage) + "%",
    "is_active": 1,
    "end_date": "2016-06-20T08:00:00-0700",
    "max_uses_per_coupon": 1
  }
  # response = requests.post("https://chickadee.tech/api/v2/discount", data=discount, headers={"Authorization": "Bearer " + lemonstand_auth_token})
  #print(response.json())
  return discount_code
