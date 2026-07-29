"""
Defines the ResearchCrew: a single-agent crew whose job is to research one
company at a time and return a structured CompanyResearch object.

Kept as its own module so it can be imported and reused (e.g. by main.py for
batch runs, or later by an email-generation crew that needs the same research
step as an upstream dependency).
"""

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from models.schemas import CompanyResearch
from tools.research_tools import research_tools


@CrewBase
class ResearchCrew:
    """Company research crew - reads config/agents.yaml and config/tasks.yaml."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def company_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["company_researcher"],
            tools=research_tools,
            verbose=True,
        )

    @task
    def research_company_task(self) -> Task:
        return Task(
            config=self.tasks_config["research_company_task"],
            output_pydantic=CompanyResearch,
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
