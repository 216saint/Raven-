"""Lightweight i18n for Raven. EN canonical, PT-BR translation.

Usage:
    from i18n import t, LANGS
    lang = st.session_state.get("lang", "en")
    st.subheader(t("settings", lang))

Unknown keys fall through to English and finally to the raw key, so adding
new strings is non-fatal even before translation lands.
"""
from __future__ import annotations

LANGS = {
    "en": "English",
    "pt": "Português (BR)",
}

LABELS: dict[str, dict[str, str]] = {
    "en": {
        # --- sidebar headers ---
        "settings": "Settings",
        "language_label": "🌐 Language",
        "model_label": "Select LLM model",
        "ollama_caption": "Locally detected Ollama / llama.cpp models are auto-added.",
        "custom_api_provider": "🔌 Custom API provider",
        "custom_api_url": "Base URL",
        "custom_api_key": "API key",
        "custom_api_model": "Model name",
        "scraping_threads": "Scraping threads",
        "max_filter": "Max results to filter",
        "max_scrape": "Max pages to scrape",
        "provider_config": "Provider configuration",
        "prompt_settings": "⚙️ Prompt settings",
        "research_domain": "Research domain",
        "custom_instructions": "Custom instructions (optional)",
        "search_profile": "🎯 Search profile",
        "profile_darkweb": "Dark Web only",
        "profile_osint": "Dark Web + OSINT (clearnet)",
        "profile_help": "OSINT adds verified clearnet sources (Intelligence X, DDoSecrets, Wayback). They use your direct connection or egress proxy — not Tor.",
        "egress_proxy": "🌐 Network egress (proxy)",
        "proxy_url_label": "HTTP/SOCKS proxy URL",
        "proxy_help": "Optional. Applied to clearweb only; .onion always uses Tor. Stored only in this session.",
        "vpn_tunnel": "🛡️ VPN tunnel",
        "vpn_disconnect": "Disconnect tunnel",
        "vpn_caption_idle": "Upload a WireGuard .conf (ProtonVPN) or OpenVPN .ovpn (IPVanish). The tunnel comes up only on click and is torn down on app exit.",
        "vpn_killswitch": "Abort pipeline if VPN drops",
        "vpn_killswitch_help": "During an active scrape, cancel pending work if the tunnel dies. Does not touch system firewall.",
        "health_checks": "Health checks",
        "btn_check_llm": "🔌 Check LLM connection",
        "btn_check_engines": "🧅 Check search engines",
        "btn_check_tor": "🧅 Check Tor proxy",
        "archive_title": "🗂️ Archive",
        "archive_runs": "runs",
        "archive_run": "run",
        "archive_load_label": "Load investigation",
        "archive_load": "📂 Load",
        "archive_delete": "🗑️ Delete",
        "archive_caption_filled": "Stored as JSON in",
        "archive_caption_empty": "No archived runs yet. Each probe is saved as JSON.",
        # --- main ---
        "brand_eyebrow": "DARK-WEB INTELLIGENCE",
        "brand_tagline": "an oracle for the unindexed deep — sees what others cannot",
        "query_placeholder": "query the deep // ransomware leak credentials onion forum...",
        "submit_button": "Probe",
        "hud_tor": "TOR",
        "hud_vpn": "VPN",
        "hud_proxy": "PROXY",
        "hud_off": "offline",
        "hud_on": "active",
        "stat_refined": "Refined Query",
        "stat_results": "Search Results",
        "stat_filtered": "Filtered Results",
        "notes_section": "📋 Notes",
        "sources_section": "🔗 Sources",
        "findings_section": "🔎 Findings",
        # --- pipeline stages ---
        "stage_load_llm": "🔄 Loading LLM...",
        "stage_refine": "🔄 Refining query...",
        "stage_search": "🔄 Searching dark web...",
        "stage_filter": "🔄 Filtering relevant results...",
        "stage_scrape": "🔄 Scraping pages...",
        "stage_summarize": "🔄 Generating findings...",
        "toast_saved": "Saved as",
        "toast_save_failed": "Could not save investigation:",
    },
    "pt": {
        "settings": "Configurações",
        "language_label": "🌐 Idioma",
        "model_label": "Modelo LLM",
        "ollama_caption": "Modelos Ollama / llama.cpp locais detectados aparecem automaticamente.",
        "custom_api_provider": "🔌 Provider de API customizado",
        "custom_api_url": "URL base",
        "custom_api_key": "Chave de API",
        "custom_api_model": "Nome do modelo",
        "scraping_threads": "Threads de scraping",
        "max_filter": "Máx resultados para filtrar",
        "max_scrape": "Máx páginas para raspar",
        "provider_config": "Configuração de providers",
        "prompt_settings": "⚙️ Configurações de prompt",
        "research_domain": "Domínio da investigação",
        "custom_instructions": "Instruções customizadas (opcional)",
        "search_profile": "🎯 Perfil de busca",
        "profile_darkweb": "Somente Dark Web",
        "profile_osint": "Dark Web + OSINT (clearnet)",
        "profile_help": "OSINT adiciona fontes clearnet verificadas (Intelligence X, DDoSecrets, Wayback Machine). Usam conexão direta ou proxy de egresso — nunca Tor.",
        "egress_proxy": "🌐 Egresso de rede (proxy)",
        "proxy_url_label": "URL do proxy HTTP/SOCKS",
        "proxy_help": "Opcional. Aplicado só ao clearweb; .onion continua via Tor. Guardado só nesta sessão.",
        "vpn_tunnel": "🛡️ Túnel VPN",
        "vpn_disconnect": "Desconectar túnel",
        "vpn_caption_idle": "Carregue um .conf WireGuard (ProtonVPN) ou .ovpn OpenVPN (IPVanish). O túnel sobe apenas quando você clica e cai ao fechar o app.",
        "vpn_killswitch": "Abortar pipeline se a VPN cair",
        "vpn_killswitch_help": "Durante um scrape, cancela trabalho pendente se o túnel morrer. Não mexe no firewall do sistema.",
        "health_checks": "Checagens de saúde",
        "btn_check_llm": "🔌 Testar LLM",
        "btn_check_engines": "🧅 Testar engines",
        "btn_check_tor": "🧅 Testar Tor",
        "archive_title": "🗂️ Arquivo",
        "archive_runs": "execuções",
        "archive_run": "execução",
        "archive_load_label": "Carregar investigação",
        "archive_load": "📂 Carregar",
        "archive_delete": "🗑️ Excluir",
        "archive_caption_filled": "Armazenado como JSON em",
        "archive_caption_empty": "Nenhuma execução arquivada. Cada busca é salva como JSON.",
        "brand_eyebrow": "INTELIGÊNCIA DA DARK WEB",
        "brand_tagline": "um oráculo do submundo não-indexado — enxerga o que outros não veem",
        "query_placeholder": "sonde o submundo // vazamento ransomware credenciais onion fórum...",
        "submit_button": "Sondar",
        "hud_tor": "TOR",
        "hud_vpn": "VPN",
        "hud_proxy": "PROXY",
        "hud_off": "inativo",
        "hud_on": "ativo",
        "stat_refined": "Query Refinada",
        "stat_results": "Resultados",
        "stat_filtered": "Filtrados",
        "notes_section": "📋 Notas",
        "sources_section": "🔗 Fontes",
        "findings_section": "🔎 Achados",
        "stage_load_llm": "🔄 Carregando LLM...",
        "stage_refine": "🔄 Refinando a query...",
        "stage_search": "🔄 Buscando na dark web...",
        "stage_filter": "🔄 Filtrando resultados...",
        "stage_scrape": "🔄 Raspando páginas...",
        "stage_summarize": "🔄 Gerando achados...",
        "toast_saved": "Salvo como",
        "toast_save_failed": "Não foi possível salvar:",
    },
}


def t(key: str, lang: str = "en") -> str:
    """Translate a key. Fallback chain: requested lang → en → raw key."""
    return LABELS.get(lang, {}).get(key) or LABELS["en"].get(key) or key


def llm_language_instruction(lang: str) -> str:
    """Return a system-prompt suffix instructing the LLM to respond in the given language."""
    if lang == "pt":
        return (
            "\n\nIMPORTANTE: Responda inteiramente em português brasileiro. "
            "Mantenha jargão técnico (CVE, IoC, TTP, ransomware, malware, etc.) "
            "em inglês quando for o termo de arte. Datas em formato ISO (YYYY-MM-DD)."
        )
    return (
        "\n\nIMPORTANT: Respond in English. Use ISO dates (YYYY-MM-DD)."
    )
