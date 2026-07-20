CREATE TABLE IF NOT EXISTS recipe_meta (
    recipe_id   TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    cuisine     TEXT DEFAULT '家常菜',
    tags        TEXT DEFAULT '[]',
    difficulty  TEXT DEFAULT '中等',
    time_min    INTEGER DEFAULT 30,
    servings    INTEGER DEFAULT 2,
    core_ingredients    TEXT DEFAULT '[]',
    seasonings          TEXT DEFAULT '[]',
    optional_ingredients TEXT DEFAULT '[]',
    equipment   TEXT DEFAULT '[]',
    allergens   TEXT DEFAULT '[]',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
