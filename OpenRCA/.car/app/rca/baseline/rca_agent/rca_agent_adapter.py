"""CanyonOS service adapter for RCA-agent.

Exposes ``RCA_Agent.run`` with the prompt modules ``rca.run_agent_standard``
selects per dataset.
"""
import threading

from loguru import logger

from rca.baseline.rca_agent.rca_agent import RCA_Agent
import rca.baseline.rca_agent.prompt.agent_prompt as ap
import rca.baseline.rca_agent.prompt.basic_prompt_Bank as bp_bank
import rca.baseline.rca_agent.prompt.basic_prompt_Market as bp_market
import rca.baseline.rca_agent.prompt.basic_prompt_Telecom as bp_telecom

BASIC_PROMPTS = {
    "Telecom": bp_telecom,
    "Bank": bp_bank,
    "Market/cloudbed-1": bp_market,
    "Market/cloudbed-2": bp_market,
}


class RCAAgent:
    def __init__(self) -> None:
        # The source runs one agent at a time; each run drives an IPython shell,
        # which is not safe to run concurrently in one process.
        self._lock = threading.Lock()

    def run(self, instruction: str, dataset: str, max_step: int, max_turn: int) -> dict:
        if dataset not in BASIC_PROMPTS:
            raise ValueError(f"Unknown dataset {dataset!r}; expected one of {sorted(BASIC_PROMPTS)}")
        with self._lock:
            agent = RCA_Agent(ap, BASIC_PROMPTS[dataset])
            prediction, trajectory, prompt = agent.run(instruction,
                                                       logger,
                                                       max_step=max_step,
                                                       max_turn=max_turn)
        return {"prediction": prediction, "trajectory": trajectory, "prompt": prompt}
