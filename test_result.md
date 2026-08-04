#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: |
  Extend the Luxembourg Family activities app with a proper polite crawler that
  discovers events from communal + venue websites Luxembourg-wide.
  Schedule: automatic 3x daily updates (05:00, 12:00, 18:00 Europe/Luxembourg).

backend:
  - task: "Robots.txt-compliant crawler infrastructure"
    implemented: true
    working: true
    file: "backend/crawler_utils.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: true
        agent: "main"
        comment: |
          New /app/backend/crawler_utils.py exposes polite_get() which:
          - Fetches + caches robots.txt per host (6h TTL)
          - Enforces per-host rate limit (max(2s, Crawl-delay))
          - Raises RobotsBlocked for disallowed URLs
          - Uses browser-like UA to avoid 403 on visitluxembourg / vdl.lu

  - task: "Sitemap-based event importer (kind=sitemap)"
    implemented: true
    working: true
    file: "backend/importers.py"
    priority: "high"
    needs_retesting: true
    status_history:
      - working: true
        agent: "main"
        comment: |
          New sitemap importer reads sitemap.xml, follows sitemap-index +
          paginated indexes, filters URLs against event-pattern regex, then
          extracts JSON-LD or falls back to OG+URL-slug date parser.
          Successfully imported 19 real Philharmonie + 9 Mudam events on first run.

  - task: "JSON-LD schema.org/Event importer (kind=json_ld)"
    implemented: true
    working: true
    file: "backend/importers.py"
    priority: "high"
    needs_retesting: true

  - task: "Scheduler switched from 24h interval to 3x daily cron"
    implemented: true
    working: true
    file: "backend/server.py"
    priority: "high"
    needs_retesting: true
    status_history:
      - working: true
        agent: "main"
        comment: |
          APScheduler CronTrigger runs run_all_active at 05:00/12:00/18:00
          Europe/Luxembourg every day.

  - task: "Admin /api/admin/sources/robots-check endpoint"
    implemented: true
    working: true
    file: "backend/server.py"
    priority: "medium"
    needs_retesting: true

  - task: "Seed script /app/backend/seed_lu_sources.py with 45 LU sources"
    implemented: true
    working: true
    file: "backend/seed_lu_sources.py"
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "main"
        comment: |
          Covers big venues (Philharmonie/Rockhal/Mudam/Neimenster/Casino/
          CAPe/Kulturfabrik/opderschmelz/Grand-Theatre/Utopia/KHN/Theatres),
          all 12 canton capitals + 12 larger communes (Differdange/Dudelange/
          Bettembourg/Petange/Sanem/Kayl/Bertrange/Strassen/Hesperange/
          Walferdange/Leudelange/Kaerjeng), family/nature venues
          (Parc Merveilleux/Sennesraich/Robbesscheier/Science Center/Naturmusee)
          and aggregators (Visit Luxembourg/Kulturkanner/echo.lu).

frontend:
  - task: "Admin sources page shows new kind types (sitemap, json_ld)"
    implemented: true
    working: "NA"
    file: "frontend/src/utils/api.ts"
    priority: "low"
    needs_retesting: true

metadata:
  created_by: main_agent
  version: 1.0
  test_sequence: 3
  run_ui: false

test_plan:
  current_focus:
    - "Robots.txt-compliant crawler infrastructure"
    - "Sitemap-based event importer (kind=sitemap)"
    - "Scheduler switched from 24h interval to 3x daily cron"
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
  - agent: "main"
    message: |
      Built out the crawler infrastructure. 53 Luxembourg sources are seeded
      and activated; a full manual run kicked off and successfully imported
      the first 33 real events (Philharmonie 19, Mudam 9, Kulturfabrik 1,
      Dudelange 1 + 3 seeded). The full run is still executing in the
      background; scheduler will run automatically 3x daily.
      Please test:
        1. GET /api/events returns the imported events (title/date/image populated).
        2. Scheduler config: verify job "importers" is registered on startup.
        3. New endpoint POST /api/admin/sources/robots-check works.
        4. Robots.txt-blocked URLs correctly result in last_status=blocked_by_robots.
