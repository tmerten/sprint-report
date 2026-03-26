import argparse
import re
import sys

from natsort import natsorted
from jira import JIRA, JIRAError
from SprintReport.jira_api import jira_api

jira_server = ""


def get_bug_id(summary):
    "Extract the bug id from a jira title which would include LP#"
    id = ""

    if "LP#" in summary:
        for char in summary[summary.find("LP#") + 3 :]:
            if char.isdigit():
                id = id + char
            else:
                break

    return id


def find_issue_in_jira_sprint(jira_api, project, sprint):
    if not jira_api or not project:
        return {}

    found_issues = {}

    request = (
        f"project = {project} "
        f'AND cf[10020] = "{sprint}" '
        f"AND status in (Done, 'In Progress', 'In review', 'To do') ORDER BY 'Epic Link'"
    )
    issues = jira_api.enhanced_search_issues(request, maxResults=0)

    epics = {}
    # For each issue in JIRA with LP# in the title
    for issue in issues:
        summary = issue.fields.summary
        issue_type = issue.fields.issuetype.name
        try:
            parent_key = issue.fields.parent.key
        except AttributeError:
            parent_key = ""
        epic_link = issue.fields.customfield_10014
        if epic_link not in epics:
            try:
                epics[epic_link] = jira_api.issue(epic_link).fields.summary
            except JIRAError:
                epics[epic_link] = "No epic"
        epic_name = epics[epic_link]
        found_issues[issue.key] = {
            "key": issue.key,
            "type": issue_type,
            "status": issue.fields.status.name,
            "epic": epic_link,
            "epic_name": epic_name,
            "parent": parent_key,
            "summary": summary,
        }

    return found_issues


def key_to_md(key):
    global jira_server
    return f"[{key}]({jira_server}/browse/{key})"


def insert_bug_link(text):
    bugid = get_bug_id(text)
    bug = f"LP#{bugid}"
    link = f"https://pad.lv/{bugid}"
    return re.sub(bug, f"[{bug}]({link})", text)


def print_jira_issue(issue):
    summary = issue["summary"]
    category = issue["type"]
    key = key_to_md(issue["key"])
    status = issue["status"]
    # epic = issue["epic"]
    if "LP#" in summary:
        summary = insert_bug_link(summary)
        print(f" - {summary}")
    else:
        print(f" - [{status}] {category}: {key} : {summary}")


def print_report_header():
    print("### **How it was made**")
    print(
        "\nThe report was made with [a fork](https://github.com/tmerten/sprint-report) ([via](https://github.com/jurekh/sprint-report)) of [https://github.com/canonical/sprint-report/](https://github.com/canonical/sprint-report/) tool, pasted as Markdown into this document. Status drop-downs were added afterwards. The fork produces a report grouped by epics instead of by issue category and uses headings compatible with this document."
    )
    print("\n```bash")
    print(
        'sprint-report MAASENG "Pulse 2026#06" | wl-copy # then "Edit" -> "paste from Markdown" in Google Docs'
    )
    print("```")
    print("\n### **Demos & Squad Updates**")
    print(
        "\n(add more demos per squad if needed; if there are no demos planned, prepare a short update from the squad about what went well and what didn’t)"
    )
    print("\n* UI")
    print("* Americas")
    print("* EMEA A")
    print("* EMEA B/C")
    print("* QA Labs")
    print("\n### **Overview**")
    print(
        "\n*Note: we should not have issues without a parent epic. If you’ve worked on one such issue, please add it to a suitable epic.*\n"
    )


def print_jira_report(jira_api, project, issues):
    print_report_header()

    if not issues:
        print("No issues found for this sprint.")
        return

    global sprint
    parent = ""
    epic = ""
    print(f"# {project} {sprint} report")

    issues = dict(
        natsorted(
            issues.items(), key=lambda i: (i[1]["parent"], i[1]["epic"], i[1]["key"])
        )
    )
    for issue in issues:
        if issues[issue]["parent"] != parent:
            parent = issues[issue]["parent"]
            parent_summary = jira_api.issue(parent).fields.summary
            print(f"\n#### {key_to_md(parent)}: {parent_summary}")
        if issues[issue]["epic"] != epic:
            epic = issues[issue]["epic"]
            if epic:
                if epic != parent:  # don't print top-level epics twice
                    # we should not be entering this branch as we group by epics...
                    print(f"\n#### {key_to_md(epic)}: {issues[issue]["epic_name"]}")
            else:
                print("\n#### Issues without an epic")
        print_jira_issue(issues[issue])


def main(args=None):
    global jira_server
    global sprint
    parser = argparse.ArgumentParser(
        description="A script to return a a Markdown report of a Jira Sprint"
    )

    parser.add_argument("project", type=str, help="key of the Jira project")
    parser.add_argument("sprint", type=str, help="name of the Jira sprint")

    opts = parser.parse_args(args)

    try:
        api = jira_api()
    except ValueError as e:
        print(f"ERROR: Cannot initialize Jira API: {e}", file=sys.stderr)
        sys.exit(1)

    jira_server = api.server

    jira = JIRA(api.server, basic_auth=(api.login, api.token))

    sprint = opts.sprint
    # Create a set of all Jira issues completed in a given sprint
    issues = find_issue_in_jira_sprint(jira, opts.project, sprint)

    print_jira_report(jira, opts.project, issues)


# =============================================================================

if __name__ == "__main__":
    main()
