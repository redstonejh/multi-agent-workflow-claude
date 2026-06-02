# Trigger — bloat flags the file, GREEN after the split

## `bloat bloated/widgets.py --max-loc 80 --max-defs 5` -> exit 1

```json
{
  "check": "bloat",
  "budgets": {
    "loc": 80,
    "defs": 5,
    "func_loc": 60,
    "branches": 40,
    "imports": 20
  },
  "files_scanned": 1,
  "over_budget_count": 1,
  "offenders": [
    {
      "file": "examples\\refactor_demo\\bloated\\widgets.py",
      "metrics": {
        "loc": 110,
        "defs": 9,
        "func_loc": 12,
        "branches": 18,
        "imports": 0
      },
      "exceeded": {
        "loc": {
          "value": 110,
          "budget": 80
        },
        "defs": {
          "value": 9,
          "budget": 5
        }
      },
      "over_budget": true,
      "severity": 1.175
    }
  ],
  "reports": [
    {
      "file": "examples\\refactor_demo\\bloated\\widgets.py",
      "metrics": {
        "loc": 110,
        "defs": 9,
        "func_loc": 12,
        "branches": 18,
        "imports": 0
      },
      "exceeded": {
        "loc": {
          "value": 110,
          "budget": 80
        },
        "defs": {
          "value": 9,
          "budget": 5
        }
      },
      "over_budget": true,
      "severity": 1.175
    }
  ],
  "passed": false,
  "note": "1 file(s) over budget \u2014 ranked worst-first; consider a behavior-preserving split (branch_count ~ cyclomatic, approx)"
}
```

## `bloat split/widgets (package) --max-loc 80 --max-defs 5` -> exit 0

```json
{
  "check": "bloat",
  "budgets": {
    "loc": 80,
    "defs": 5,
    "func_loc": 60,
    "branches": 40,
    "imports": 20
  },
  "files_scanned": 5,
  "over_budget_count": 0,
  "offenders": [],
  "reports": [
    {
      "file": "examples\\refactor_demo\\split\\widgets\\__init__.py",
      "metrics": {
        "loc": 17,
        "defs": 0,
        "func_loc": 0,
        "branches": 0,
        "imports": 4
      },
      "exceeded": {},
      "over_budget": false,
      "severity": 0
    },
    {
      "file": "examples\\refactor_demo\\split\\widgets\\listx.py",
      "metrics": {
        "loc": 20,
        "defs": 2,
        "func_loc": 7,
        "branches": 4,
        "imports": 0
      },
      "exceeded": {},
      "over_budget": false,
      "severity": 0
    },
    {
      "file": "examples\\refactor_demo\\split\\widgets\\mathx.py",
      "metrics": {
        "loc": 16,
        "defs": 2,
        "func_loc": 5,
        "branches": 3,
        "imports": 0
      },
      "exceeded": {},
      "over_budget": false,
      "severity": 0
    },
    {
      "file": "examples\\refactor_demo\\split\\widgets\\money.py",
      "metrics": {
        "loc": 21,
        "defs": 2,
        "func_loc": 8,
        "branches": 2,
        "imports": 0
      },
      "exceeded": {},
      "over_budget": false,
      "severity": 0
    },
    {
      "file": "examples\\refactor_demo\\split\\widgets\\text.py",
      "metrics": {
        "loc": 38,
        "defs": 3,
        "func_loc": 12,
        "branches": 9,
        "imports": 0
      },
      "exceeded": {},
      "over_budget": false,
      "severity": 0
    }
  ],
  "passed": true,
  "note": "every file is within budget"
}
```
