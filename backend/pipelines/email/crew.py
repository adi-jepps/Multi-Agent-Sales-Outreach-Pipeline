"""
Defines the EmailCrew: a single-agent crew whose job is to write one
personalized outreach email at a time and return a structured EmailDraft.

Mirrors pipelines/research/crew.py's ResearchCrew shape - same CrewBase
pattern, just a different agent/task/output and no tools (pure writing task,
no scraping or search needed).
"""

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from models.schemas import EmailDraft


@CrewBase
class EmailCrew:
    """Email personalization crew - reads config/agents.yaml and config/tasks.yaml."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def email_copywriter(self) -> Agent:
        return Agent(
            config=self.agents_config["email_copywriter"],
            verbose=True,
        )

    @task
    def personalize_email_task(self) -> Task:
        return Task(
            config=self.tasks_config["personalize_email_task"],
            output_pydantic=EmailDraft,
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
