# Office dashboard template

`office.html` is the product office page that the `office-manager` session publishes as a private claude.ai Artifact (capabilities `db` + `user` + `sample`; `sample` gives the quick replies).

Every requirement for the page and its data layout is in `SPEC.md`.

- Publish `office.html` as the page and every file under `assets/` with the same relative paths (Artifact `files`).
- The page title is "Product Office". To show the product's name, write `meta/office` with `{ "product_en": "<name>" }` to the page's database.
- The whole page is English, left to right. Agents show by `name_en`, `role_en`, `doing_en`; tasks by `feature` and `title_en`. Full requirements: playbook card 0d. Font: Dubai (`assets/fonts/`). Thmanyah is not used because its license forbids hosting the font files.
- Data collections: `agents`, `tasks`, `messages`, `sessions` (schema in the playbook, section 8, card 0d).
- Rooms: the manager's office (owner + `office-manager` as the assistant; agents in state `waiting` visit here), the meeting room (agents talking to each other and members of open task sessions sit at the table), the main office (working and blocked agents on chairs at desks), the games room (done and not started agents), and the idle room (agents with no activity for more than 3 days sit there on chairs, still, with "Idle since <date>"). Agents walk between rooms when their state changes.
- Task sessions: the owner opens one from a task when something isn't clear; it is private to that question and closes when it is solved.

Art: the owner's own pictures, cut out with `tools/cut/` (see `SPEC.md`, "Characters and rooms"). Every picture carries the credit tag `@Abdulwahabdev`; see the root `LICENSE`.

Check before a push: serve a copy of the page with demo data and run `node tools/check/smoke.mjs <url>` (set `PLAYWRIGHT` to Playwright's `index.mjs` if the package is not installed). It opens every tab and the main dialogs and fails on any page error or empty panel; a phone pass at 400 px fails on sideways scroll, on anything covering the chat's Send button, or on a task over 150 ms.
