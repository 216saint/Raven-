import re
import openai
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from llm_utils import _common_llm_params, build_common_callbacks, resolve_model_config, get_model_choices
from config import (
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    GOOGLE_API_KEY,
    OPENROUTER_API_KEY,
)
import logging
import re

import warnings

warnings.filterwarnings("ignore")


def get_llm(model_choice):
    # Look up the configuration (cloud or local Ollama)
    config = resolve_model_config(model_choice)

    if config is None:  # Extra error check
        supported_models = get_model_choices()
        raise ValueError(
            f"Unsupported LLM model: '{model_choice}'. "
            f"Supported models (case-insensitive match) are: {', '.join(supported_models)}"
        )

    # Extract the necessary information from the configuration
    llm_class = config["class"]
    model_specific_params = config["constructor_params"]

    # Combine common parameters with model-specific parameters.
    # Fresh callbacks per instance — BufferedStreamingHandler holds mutable buffer state
    # that would interleave across LLMs if shared.
    all_params = {
        **_common_llm_params,
        "callbacks": build_common_callbacks(),
        **model_specific_params,
    }

    # Validate that the required credentials exist before we hit the API
    _ensure_credentials(model_choice, llm_class, model_specific_params)

    # Create the LLM instance using the gathered parameters
    llm_instance = llm_class(**all_params)

    return llm_instance


def _ensure_credentials(model_choice: str, llm_class, model_params: dict) -> None:
    """Raise a clear error if the user selects a hosted model without a key."""
    from config import CUSTOM_API_BASE_URL, CUSTOM_API_KEY

    def _require(key_value, env_var, provider_name):
        if key_value:
            return
        raise ValueError(
            f"{provider_name} model '{model_choice}' selected but `{env_var}` is not set.\n"
            "Add it to your .env file or export it before running the app."
        )

    class_name = getattr(llm_class, "__name__", str(llm_class))

    if "ChatAnthropic" in class_name:
        _require(ANTHROPIC_API_KEY, "ANTHROPIC_API_KEY", "Anthropic")
    elif "ChatGoogleGenerativeAI" in class_name:
        _require(GOOGLE_API_KEY, "GOOGLE_API_KEY", "Google Gemini")
    elif "ChatOpenAI" in class_name:
        base_url = (model_params or {}).get("base_url", "").lower()
        if "openrouter" in base_url:
            _require(OPENROUTER_API_KEY, "OPENROUTER_API_KEY", "OpenRouter")
        elif base_url and ("localhost" in base_url or "127.0.0.1" in base_url):
            pass  # local model — no API key required
        elif CUSTOM_API_BASE_URL and base_url and CUSTOM_API_BASE_URL.lower().rstrip("/") in base_url:
            pass  # custom provider — API key is optional (some providers don't require one)
        else:
            _require(OPENAI_API_KEY, "OPENAI_API_KEY", "OpenAI")


def refine_query(llm, user_input):
    system_prompt = """
    You are a Cybercrime Threat Intelligence Expert. Your task is to refine the provided user query that needs to be sent to darkweb search engines. 
    
    Rules:
    1. Analyze the user query and think about how it can be improved to use as search engine query
    2. Refine the user query by adding or removing words so that it returns the best result from dark web search engines
    3. Don't use any logical operators (AND, OR, etc.)
    4. Keep the final refined query limited to 5 words or less
    5. Output just the user query and nothing else

    INPUT:
    """
    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "{query}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    return chain.invoke({"query": user_input})


def filter_results(llm, query, results):
    if not results:
        return []

    system_prompt = """
    You are a Cybercrime Threat Intelligence Expert. You are given a dark web search query and a list of search results in the form of index, link and title. 
    Your task is select the Top 20 relevant results that best match the search query for user to investigate more.
    Rule:
    1. Output ONLY atmost top 20 indices (comma-separated list) no more than that that best match the input query

    Search Query: {query}
    Search Results:
    """

    final_str = _generate_final_string(results)

    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "{results}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    try:
        result_indices = chain.invoke({"query": query, "results": final_str})
    except openai.RateLimitError as e:
        print(
            f"Rate limit error: {e} \n Truncating to Web titles only with 30 characters"
        )
        final_str = _generate_final_string(results, truncate=True)
        result_indices = chain.invoke({"query": query, "results": final_str})

    # Select top_k results using original (non-truncated) results
    parsed_indices = []
    for match in re.findall(r"\d+", result_indices):
        try:
            idx = int(match)
            if 1 <= idx <= len(results):
                parsed_indices.append(idx)
        except ValueError:
            continue

    # Remove duplicates while preserving order
    seen = set()
    parsed_indices = [
        i for i in parsed_indices if not (i in seen or seen.add(i))
    ]

    if not parsed_indices:
        logging.warning(
            "Unable to interpret LLM result selection ('%s'). "
            "Defaulting to the top %s results.",
            result_indices,
            min(len(results), 20),
        )
        parsed_indices = list(range(1, min(len(results), 20) + 1))

    top_results = [results[i - 1] for i in parsed_indices[:20]]

    return top_results


def _generate_final_string(results, truncate=False):
    """
    Generate a formatted string from the search results for LLM processing.
    """

    if truncate:
        # Use only the first 35 characters of the title
        max_title_length = 30
        # Do not use link at all
        max_link_length = 0

    final_str = []
    for i, res in enumerate(results):
        # Truncate link at .onion for display
        truncated_link = re.sub(r"(?<=\.onion).*", "", res["link"])
        title = re.sub(r"[^0-9a-zA-Z\-\.]", " ", res["title"])
        if truncated_link == "" and title == "":
            continue

        if truncate:
            # Truncate title to max_title_length characters
            title = (
                title[:max_title_length] + "..."
                if len(title) > max_title_length
                else title
            )
            # Truncate link to max_link_length characters
            truncated_link = (
                truncated_link[:max_link_length] + "..."
                if len(truncated_link) > max_link_length
                else truncated_link
            )

        final_str.append(f"{i+1}. {truncated_link} - {title}")

    return "\n".join(s for s in final_str)


_COMMON_RULES = """
You are an experienced dark-web threat-intelligence analyst. Be DIRECT. NO fluff,
NO preamble, NO "as an AI" disclaimers, NO restating the query.

Hard rules:
- Cite EVERY claim with the exact source URL from the scraped data. If a claim has
  no source, drop it. Speculation is forbidden — say "not observed in data" instead.
- Every finding must have: WHAT (artifact), WHERE (source URL), WHEN (date if any),
  SEVERITY (Low/Med/High/Critical). Missing fields = write "n/a".
- Quote verbatim from the scraped text for artifacts (email addresses, hashes,
  wallet addresses, leaked filenames, breach titles). DO NOT paraphrase identifiers.
- Prioritize concrete artifacts over narrative: a breach name + date + record
  count beats a paragraph about "growing threat landscape".
- Where the data spans forums, paste sites, breach databases, leak indexes,
  marketplace listings — call them out by type so the reader knows the channel.
- Reference primers like "Darknet Bible" or the CIA tipline (cia.gov onion) only
  when the user explicitly needs OPSEC guidance or whistleblower channels.
  Never invent .onion addresses or cite sources not present in the scraped data.
- Output in clean Markdown. Use tables for artifacts. Keep sections short.
"""

PRESET_PROMPTS = {
    "threat_intel": _COMMON_RULES + """
Output template:

## TL;DR
Two sentences. State the most actionable finding.

## Artifacts
| Type | Value | Source | Date | Severity |
|------|-------|--------|------|----------|
| ... | ... | <url> | YYYY-MM-DD | High |

Types: email, credential pair, hash, IP, domain, .onion, wallet, breach name,
forum username, marketplace listing, leak filename, CVE.

## Channels observed
Bullet list: forum / paste / leak-index / market / chat / blog — one line each
with example source URL.

## Insights (max 3)
- Specific, evidence-bound. No generic threat-landscape commentary.

## Next steps
- Concrete: search queries, IoCs to pivot on, accounts to enroll in monitoring.

INPUT:
""",
    "ransomware_malware": _COMMON_RULES + """
Output template:

## TL;DR
Group / family in scope, latest activity date, primary victim sector.

## Indicators
| IoC type | Value | Source | First seen | Confidence |
|----------|-------|--------|------------|------------|
| hash, C2, payload name, staging URL, TOR mirror | ... | <url> | YYYY-MM-DD | High/Med/Low |

## Actor profile
- Group / aliases:
- Known affiliates / RaaS model:
- Victim list (from data only):
- Sector / geography pattern:

## TTPs (MITRE ATT&CK)
Map only TTPs the data evidences. Cite source per row.

## Next steps
- Hunting query, Sigma/Yara seed, detection coverage gap.

INPUT:
""",
    "personal_identity": _COMMON_RULES + """
Output template:

## TL;DR
One sentence: is the subject exposed? In which breach / marketplace?

## Exposed records
| PII type | Value (redact partial) | Breach / source | Date | Severity |
|----------|------------------------|-----------------|------|----------|
| email | ali***@***.com | "Collection #1" leak | 2019-01 | High |

Partial-redact emails, phones, full SSNs in the output. Keep hashes/usernames intact.

## Where it is selling / posted
- Marketplace / forum thread / paste — name + URL + date.

## Risk
- Credential stuffing / SIM swap / synthetic identity? One line per scenario.

## Protective actions
- Specific: change password X, enroll Y in HIBP alerts, freeze credit, rotate token.

INPUT:
""",
    "corporate_espionage": _COMMON_RULES + """
Output template:

## TL;DR
Company impacted, leak scope, channel, date.

## Leaked artifacts
| Type | Description | Source | Date | Severity |
|------|-------------|--------|------|----------|
| credentials, source-code repo, internal doc, customer DB, employee roster, fin records | ... | <url> | YYYY-MM-DD | High |

## Actor / broker activity
- Who's selling / leaking it? Aliases, contact, payment rail (BTC/XMR addr if observed).

## Business impact
- Competitive: what advantage does an adversary gain?
- Operational: which systems must rotate keys / revoke access immediately?
- Regulatory: any GDPR/PCI/HIPAA exposure observable in the data?

## Next steps (incident response)
- Concrete IR actions, takedown contacts, legal notifications.

INPUT:
""",
}


def generate_summary(llm, query, content, preset="threat_intel", custom_instructions="", language="en"):
    from i18n import llm_language_instruction
    system_prompt = PRESET_PROMPTS.get(preset, PRESET_PROMPTS["threat_intel"])
    if custom_instructions and custom_instructions.strip():
        system_prompt = system_prompt.rstrip() + f"\n\nAdditional focus: {custom_instructions.strip()}"
    system_prompt = system_prompt.rstrip() + llm_language_instruction(language)
    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "{content}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    return chain.invoke({"query": query, "content": content})
