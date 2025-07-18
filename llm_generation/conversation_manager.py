from typing import Dict, List


class ConversationManager:
    def __init__(self):
        self.history: List[Dict[str, str]] = []

    def add_user_message(self, content: str):
        self.history.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str):
        self.history.append({"role": "assistant", "content": content})

    def add_system_message(self, content: str):
        self.history.append({"role": "system", "content": content})

    def get_history(self):
        return self.history

    def clear_history(self):
        self.history.clear()
