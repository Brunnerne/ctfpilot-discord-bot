import requests
from github import Github, Issue

class GithubHandler:
    def __init__(self, github_token: str, repo_name: str):
        self.github_token = github_token
        self.api_url = "https://api.github.com/graphql"
        self.headers = {"Authorization": f"Bearer {self.github_token}"}
        self.gh = Github(github_token)
        self.repo = self.gh.get_repo(repo_name)

    def get_milestone(self, title: str):
        try:
            milestones = list(self.repo.get_milestones())
            for m in milestones:
                if m.title == title:
                    return m
        except Exception:
            pass
        return None

    def create_issue(self, name, body, labels, milestone=None):
        if milestone:
            return self.repo.create_issue(title=name, body=body, labels=labels, milestone=milestone)
        else:
            return self.repo.create_issue(title=name, body=body, labels=labels)

    def get_issue(self, issue_number):
        return self.repo.get_issue(number=issue_number)

    def set_issue_labels(self, issue, labels):
        issue.set_labels(*labels)

    def get_workflow(self, workflow_path):
        return self.repo.get_workflow(workflow_path)

    def trigger_workflow(self, workflow_path, ref, inputs):
        workflow = self.get_workflow(workflow_path)
        if not workflow:
            print(f"[ERROR] Workflow not found: {workflow_path}")
            raise Exception(f"Workflow not found: {workflow_path}")
        try:
            workflow.create_dispatch(ref=ref, inputs=inputs)
        except Exception as e:
            print(f"[ERROR] Failed to trigger workflow: {e}")
            raise Exception(f"Failed to trigger workflow: {e}")
        

    def get_status_field_and_option_id(self, project_id, status_name="Idea"):
        # Fetch the status field ID and the option ID for the given status name
        query = '''
        query($projectId:ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              fields(first: 20) {
                nodes {
                  ... on ProjectV2SingleSelectField {
                    id
                    name
                    options {
                      id
                      name
                    }
                  }
                }
              }
            }
          }
        }
        '''
        variables = {"projectId": project_id}
        r = requests.post(self.api_url, json={"query": query, "variables": variables}, headers=self.headers)
        if not r.ok:
            print(f"[ERROR] GraphQL status field query failed: {r.status_code} {r.text}")
            return None, None
        try:
            data = r.json()
        except Exception as e:
            print(f"[ERROR] Could not decode GraphQL response: {e}, content: {r.text}")
            return None, None
        node = data.get('data', {}).get('node')
        if not node:
            print(f"[ERROR] No 'node' in GraphQL response: {data}")
            return None, None
        fields = node.get('fields', {}).get('nodes', [])
        for field in fields:
            if field.get('name') == 'Status':
                status_field_id = field['id']
                found_options = [option.get('name') for option in field.get('options', [])]
                for option in field.get('options', []):
                    if option.get('name') == status_name:
                        return status_field_id, option['id']
                print(f"[ERROR] Status option '{status_name}' not found. Available options: {found_options}")
                return None, None
        print(f"[ERROR] Status field not found in project fields: {[f.get('name') for f in fields]}")
        return None, None

    def add_issue_to_project_and_set_status(self, issue_node_id, project_id, status_name="Idea"):
        # Step 1: Add issue to project
        add_item_query = '''
        mutation AddIssueToProject($projectId:ID!, $contentId:ID!) {
          addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
            item { id }
          }
        }
        '''
        variables = {"projectId": project_id, "contentId": issue_node_id}
        r = requests.post(self.api_url, json={"query": add_item_query, "variables": variables}, headers=self.headers)
        item_id = None
        if r.ok:
            try:
                resp_json = r.json()
            except Exception as e:
                print(f"[ERROR] Could not decode addProjectV2ItemById response: {e}, content: {r.text}")
                return False, "Failed to decode addProjectV2ItemById response."
            item_id = resp_json.get('data', {}).get('addProjectV2ItemById', {}).get('item', {}).get('id')
        if not item_id:
            print(f"[ERROR] Failed to add issue to project. Response: {r.text}")
            return False, "Failed to add issue to project."
        # Step 2: Get status field and option id
        status_field_id, status_option_id = self.get_status_field_and_option_id(project_id, status_name)
        if not status_field_id or not status_option_id:
            return False, "Could not find status field or option in project."
        # Step 3: Set status field
        set_status_query = '''
        mutation SetStatus($itemId:ID!, $fieldId:ID!, $optionId: String!) {
          updateProjectV2ItemFieldValue(
            input: {projectId: \"%s\", itemId: $itemId, fieldId: $fieldId, value: { singleSelectOptionId: $optionId }}
          ) { projectV2Item { id } }
        }
        ''' % project_id
        variables = {"itemId": item_id, "fieldId": status_field_id, "optionId": status_option_id}
        r2 = requests.post(self.api_url, json={"query": set_status_query, "variables": variables}, headers=self.headers)
        if r2.ok:
            return True, None
        else:
            print(f"[ERROR] Failed to set status field. Response: {r2.text}")
            return False, "Failed to set status field."

    def get_project_node_id(self, org: str, project_number: int, is_org: bool = True):
        if is_org:
            query = '''
            query($org: String!, $number: Int!) {
              organization(login: $org) {
                projectV2(number: $number) { id title }
              }
            }
            '''
            variables = {"org": org, "number": project_number}
        else:
            query = '''
            query($user: String!, $number: Int!) {
              user(login: $user) {
                projectV2(number: $number) { id title }
              }
            }
            '''
            variables = {"user": org, "number": project_number}
        r = requests.post(self.api_url, json={"query": query, "variables": variables}, headers=self.headers)
        if not r.ok:
            print(f"[ERROR] Failed to fetch project node id: {r.status_code} {r.text}")
            return None
        try:
            data = r.json()
        except Exception as e:
            print(f"[ERROR] Could not decode project node id response: {e}, content: {r.text}")
            return None
        if is_org:
            project = data.get('data', {}).get('organization', {}).get('projectV2')
        else:
            project = data.get('data', {}).get('user', {}).get('projectV2')
        if project and project.get('id'):
            return project['id']
        print(f"[ERROR] Project node id not found in response: {data}")
        return None

    def get_issue_project_status(self, issue_number, project_id, issue_node_id):
        """Return the project status for the given issue in the given project, or 'Unknown' if not found."""
        query = '''
        query($projectId:ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              items(first: 100) {
                nodes {
                  content {
                    ... on Issue {
                      id
                      number
                    }
                  }
                  fieldValues(first: 100) {
                    nodes {
                      ... on ProjectV2ItemFieldSingleSelectValue {
                        field {
                          ... on ProjectV2SingleSelectField {
                            name
                          }
                        }
                        name
                      }
                    }
                  }
                }
              }
            }
          }
        }
        '''
        variables = {"projectId": project_id}
        r = requests.post(self.api_url, json={"query": query, "variables": variables}, headers=self.headers)
        if not r.ok:
            print(f"[ERROR] Failed to fetch project status: {r.text}")
            return 'Unknown'
        try:
            data = r.json()
            node = data.get('data', {}).get('node', {})
            items = node.get('items', {}).get('nodes', []) if node else []
            for item in items:
                content = item.get('content', {}) if item else {}
                if content is None:
                    continue
                if str(content.get('number', '')) == str(issue_number):
                    field_values = item.get('fieldValues', {}).get('nodes', []) if item.get('fieldValues') else []
                    for field_value in field_values:
                        field = field_value.get('field', {}) if field_value else {}
                        if field.get('name', '') == 'Status':
                            return field_value.get('name', 'Unknown')
        except Exception as e:
            print(f"[ERROR] Exception in get_issue_project_status: {e}")
        return 'Unknown'

    def parse_issue(self, issue: Issue.Issue):
        """Parse the issue to extract relevant information."""
        if not issue:
            return None
        return {
            "number": issue.number,
            "title": issue.title,
            "body": issue.body,
            "state": issue.state,
            "labels": [label.name for label in issue.labels],
            "assignees": [assignee.login for assignee in issue.assignees],
            "created_at": issue.created_at.isoformat(),
            "updated_at": issue.updated_at.isoformat(),
            "closed_at": issue.closed_at.isoformat() if issue.closed_at else None,
        }

    def get_difficulty(self, issue: Issue.Issue):
        """Get the difficulty label from the issue."""
        if not issue:
            return None
        for label in issue.labels:
            if label.name.startswith("Difficulty: "):
                return label.name.split("Difficulty: ")[1]
        return None
      
    def get_category(self, issue: Issue.Issue):
        """Get the category label from the issue."""
        if not issue:
            return None
        for label in issue.labels:
            if label.name.startswith("Category: "):
                return label.name.split("Category: ")[1]
        return None
