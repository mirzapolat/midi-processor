# Implement

Given the user's request in $ARGUMENTS (or the most recent message if empty), follow this process exactly:

## 1. Plan — create a todo list

Break the request into discrete, actionable tasks using TaskCreate. Each task should be one logical unit of work (a single feature, fix, or refactor). Do not start any implementation yet.

## 2. Implement — work through tasks one by one

For each task in order:
- Mark it `in_progress` with TaskUpdate before touching any code.
- Read all relevant files before making changes.
- Make the minimal change that completes the task — no scope creep.
- Mark it `completed` with TaskUpdate immediately after finishing.

## 3. Test

After all tasks are completed, run the application or any available tests to verify nothing is broken:
- For this project: `cd /Users/mirzapolat/Downloads/midi-exporter && python -m py_compile midi_splitter.py && echo "Syntax OK"`
- Report any errors and fix them (create a new task if the fix is non-trivial).

## 4. Dead code cleanup

Scan the codebase for code that is now unreachable or unused as a direct result of the changes just made:
- Unused imports, classes, functions, constants, or variables
- Branches or conditions that can never be reached anymore
- Remove anything found. Do not remove code unrelated to this session's changes.

Mark a final cleanup task completed when done.
