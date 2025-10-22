# Guide: Adding a New Adapter (DTC or API-based) to Ceneca

This guide documents all the steps and code locations required to make a new adapter (like ShipRocket, PayU, EaseBuzz, Uniware, etc.) visible and accessible to the LLM/orchestrator system. Use this as a checklist for future integrations.

---

## 1. **Create the Adapter**
- **File:** `server/agent/db/adapters/<adapter_name>.py`
- **What to do:** Implement the adapter class with methods for authentication, schema discovery, and data access. Follow the pattern in `shiprocket.py`.

---

## 2. **Register the Adapter in the Adapters Package**
- **File:** `server/agent/db/adapters/__init__.py`
- **What to do:** Import and expose the new adapter class so it can be dynamically loaded.

---

## 3. **Add to Data Source Discovery**
- **File:** `server/agent/db/registry/config_sources.py`
- **What to do:**
  - Add logic in `get_data_sources()` to detect and yield configuration for the new adapter from `config.yaml` or `auth-config.yaml`.
  - Ensure the adapter's config block is documented in the code and in the sample config files.

---

## 4. **Update Introspection Logic**
- **File:** `server/agent/db/registry/introspect_worker.py`
- **What to do:**
  - Add an introspection function for the new adapter if needed.
  - Ensure it can fetch schema/tables/fields and register them in the registry.

---

## 5. **Update Operation Factory**
- **File:** `server/agent/db/orchestrator/plans/factory.py`
- **What to do:**
  - In `create_operation()`, add a case for the new adapter to construct the correct operation class and parameters.
  - In `create_plan_from_dict()`, add parameter mapping for the new adapter.
  - In the type inference section, add logic to infer the adapter type from operation class names.

---

## 6. **Update Settings/Config Loader**
- **File:** `server/agent/config/settings.py`
- **What to do:**
  - Add properties to load the adapter's URI and credentials from `config.yaml` or environment variables.
  - Update the `connection_uri` property to handle the new adapter type.

---

## 7. **Update API Capabilities (Optional)**
- **File:** `server/agent/api/endpoints.py`
- **What to do:**
  - Add the new adapter to the `supported_databases` list and sample queries if you want it to show up in API metadata.

---

## 8. **Run Introspection**
- **Command:**
  ```bash
  # Activate venv and run introspection for the new adapter
  source venv311/bin/activate
  python -c "from agent.db.registry.introspect_worker import run_introspection; from agent.db.registry.config_sources import get_data_sources; import asyncio; sources = get_data_sources(); new_sources = [s for s in sources if s['type'] == '<adapter_name>']; asyncio.run(run_introspection(new_sources))"
  ```
- **What to do:**
  - This will register the new adapter's schema in the registry so the LLM can discover it.

---

## 9. **Test End-to-End**
- **API Test:**
  - Use the `/api/agent/langgraph/stream` endpoint with a query targeting the new adapter.
  - Confirm the adapter is discovered and the correct data is returned.

---

## 10. **Troubleshooting Checklist**
- If the adapter is not discovered:
  - Check `config.yaml` and credentials files for correct config.
  - Check `settings.py` for missing URI/credentials logic.
  - Check the registry (run `check_registry.py`) to see if the adapter is registered.
  - Check the introspection logs for errors.
  - Try a more explicit prompt to force the LLM to use the new adapter.

---

## **Summary Table**
| Step | File/Location | What to Edit |
|------|---------------|--------------|
| 1    | adapters/<adapter>.py | Implement adapter class |
| 2    | adapters/__init__.py | Register adapter |
| 3    | registry/config_sources.py | Add to data source discovery |
| 4    | registry/introspect_worker.py | Add introspection logic |
| 5    | orchestrator/plans/factory.py | Add to operation factory |
| 6    | config/settings.py | Add config/URI logic |
| 7    | api/endpoints.py | Add to API metadata (optional) |
| 8    | CLI | Run introspection |
| 9    | API | Test end-to-end |

---

**This guide should be updated with any new patterns or requirements as the system evolves.** 