from core.memory import MemoryStore

store = MemoryStore("data/sessions.db")

session_id = store.save_mock_session()

print("Inserted:", session_id)
print("Count:", store.session_count())