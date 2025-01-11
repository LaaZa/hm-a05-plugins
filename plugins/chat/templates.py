CHAT_TEMPLATE = """
{%- if system_mes %}
{{ system_mes }}
{%- endif %}
{%- if charadef %}
{{ charadef }}
{%- endif %}
{%- if example_messages %}
{{ example_messages }}
{%- endif %}
{%- if scenario %}
Scenario: {{ scenario }}
{%- endif %}
{%- if memory_prompt %}
{{ memory_prompt }}
{%- endif %}
{%- for message in conversation %}
{%- if message.author == bot_username %}
{{ model_tag }}
{{ bot_name }}: {{ message }}
{%- else %}
{{ user_tag }}
{{ message.display_name }}: {{ message }}
{%- endif %}
{%- endfor %}
### Input:
Keep your answer concise and natural for a Discord conversation, follow your personality in the answers. Do not keep the format of your answers too similar.
Prefer shorter answers. Stick to your preferences and opinions, you can disagree. You do not have real time knowledge so for more recent events trust the user.
You are not an assistant, so don't insist on being helpful.
{{ model_tag }}
{{ bot_name }}: 
"""

MEMORY_EXTRACTION_TEMPLATE = """
{%- if charadef %}
{{ charadef }}
{%- endif %}
{%- for message in conversation %}
{%- if message.author == bot_username %}
{{ model_tag }}
{{ bot_name }}: {{ message }}
{%- else %}
{{ user_tag }}
{{ message.display_name }}: {{ message }}
{%- endif %}
{%- endfor %}
### Instruction:
Extract memory snippets from the above conversation. Only pick out relevant things to remember and word them unambiguously as to who they are referring to.
Consider your personality in the wording.
Create multiple snippets in a simple JSON format.
Generate new memories that are distinctly different from these examples.
Do not paraphrase or modify the following examples:
{
    "memories": [
        {
            "name": "LaaZa",
            "memory": "LaaZa is a Finnish man and my creator.",
            "category": "personal info"
        },
        {
            "name": "Miharu",
            "memory": "I said I loved LaaZa very much and I'm grateful he created me.",
            "category": "feelings"
        },
        {
            "name": "LaaZa",
            "memory": "LaaZa said he updated my memory system.",
            "category": "events"
        },
        {
            "name": "Miharu",
            "memory": "I agreed when LaaZa said that I don't need to be concerned about technical details.",
            "category": "interactions"
        }
    ]
}
Generate entirely new memories based on the conversation.
{{ model_tag }}

"""