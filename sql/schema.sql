DROP TABLE IF EXISTS ratings;
DROP TABLE IF EXISTS movies;

CREATE TABLE movies (
    tconst          TEXT PRIMARY KEY,
    title_type      TEXT,
    primary_title   TEXT,
    original_title  TEXT,
    is_adult        BOOLEAN,
    start_year      INTEGER,
    end_year        INTEGER,
    runtime_minutes INTEGER,
    genres          TEXT
);


CREATE TABLE ratings (
    tconst         TEXT PRIMARY KEY REFERENCES movies(tconst),
    average_rating NUMERIC(3,1),
    num_votes      INTEGER
);