-- ════════════════════════════════════════════════════════════════════════════
-- candidates.sql (v4)
-- ════════════════════════════════════════════════════════════════════════════
-- v4 dodaje:
--   • last_club_id, last_team_id — wybrane chronologicznie po match_date
--     (zamiast po liczbie minut). Jeśli zawodnik zmienił klub w sezonie,
--     widzimy KLUB AKTUALNY, nie ten z większą liczbą minut.
--   • dominant_club_id zachowane jako fallback
-- ════════════════════════════════════════════════════════════════════════════

WITH active_candidates AS MATERIALIZED (
    SELECT
        m.player_id,
        MAX(s.age) AS current_age
    FROM pm_player_match_stats m
    JOIN pm_player_match_score s
        ON m.match_id  = s.match_id
       AND m.player_id = s.player_id
    WHERE m.season_id = 'e9d66181-d03e-4bb3-b889-4da848f4831d'
      AND m.league_id IN (
            '5cc45e5f-744b-428c-b8af-cdefca38de29',
            'c164ca31-22e4-43fc-9e30-4f3bcc2b7d72',
            'a0583713-115c-4aa5-90f2-140f6eaece15',
            'c5afdf4b-b449-4ef3-acf5-dded47fc5f58',
            '63d04023-727a-4c0c-a8c6-4154fe1104b7',
            'b7d2c55b-e2af-44e2-9df2-3f6e05dc1768',
            '895016b3-4fa6-4a68-aa41-5035f9ebef8e',
            'bf74d613-4cc6-4115-ad03-fac139dee351',
            '8e70e715-3f0f-4481-a01d-51fb7b9aee90',
            '279a6c2b-0504-4be3-9386-3c1ca785d11d',
            '8104ee44-740c-4f6c-8fc3-3bbcf2b3b0e7',
            '436dc4c6-bc94-4d30-ae92-1113d6d4eee3',
            '5b788871-3d38-4073-9500-fcfa4d1b4270',
            'f19d92f4-14f7-45ab-884f-90da0d03f4a0',
            '823a45df-052b-4cd5-a060-32ed52921992',
            '75b51f36-93fd-49cb-86d3-6086dc88081b',
            '317d1eb3-4873-4749-91b5-edb2d0cd4375',
            'adf4ca7f-46ef-4aff-a7a0-3e7cc614c59d'
      )
      AND s.age BETWEEN 15 AND 26
      AND m.is_keeper = false
      AND m.minutes > 0
    GROUP BY m.player_id
    HAVING SUM(m.minutes) >= 600
),
tracked_leagues AS (
    SELECT _id FROM (VALUES
        ('337bb869-0b42-484f-8eca-0c8842a13ec9'), ('50e40483-e8dc-4e4b-9f58-a83f93a54d9a'),
        ('5f26d625-e72e-4aa5-9ffe-451025c18e3a'), ('5cc45e5f-744b-428c-b8af-cdefca38de29'),
        ('c164ca31-22e4-43fc-9e30-4f3bcc2b7d72'), ('a0583713-115c-4aa5-90f2-140f6eaece15'),
        ('c5afdf4b-b449-4ef3-acf5-dded47fc5f58'), ('63d04023-727a-4c0c-a8c6-4154fe1104b7'),
        ('b7d2c55b-e2af-44e2-9df2-3f6e05dc1768'), ('895016b3-4fa6-4a68-aa41-5035f9ebef8e'),
        ('bf74d613-4cc6-4115-ad03-fac139dee351'), ('8e70e715-3f0f-4481-a01d-51fb7b9aee90'),
        ('279a6c2b-0504-4be3-9386-3c1ca785d11d'), ('8104ee44-740c-4f6c-8fc3-3bbcf2b3b0e7'),
        ('436dc4c6-bc94-4d30-ae92-1113d6d4eee3'), ('5b788871-3d38-4073-9500-fcfa4d1b4270'),
        ('f19d92f4-14f7-45ab-884f-90da0d03f4a0'), ('823a45df-052b-4cd5-a060-32ed52921992'),
        ('75b51f36-93fd-49cb-86d3-6086dc88081b'), ('317d1eb3-4873-4749-91b5-edb2d0cd4375'),
        ('adf4ca7f-46ef-4aff-a7a0-3e7cc614c59d'), ('7c5a509a-2dac-46a7-9a37-54d48719758b'),
        ('9d41a9e1-aa66-4e2c-9f33-6f4b01139837'), ('811e1235-dc60-4db3-bf68-ee9b43d8370c'),
        ('bf404c9a-f13c-4835-885a-43ba3774850c')
    ) AS t(_id)
),
candidate_history AS (
    SELECT
        m.player_id,
        p.firstname || ' ' || p.lastname AS player_name,
        m.season_id,
        m.league_id,
        MAX(s.age)                  AS age_in_season,
        SUM(m.minutes)              AS total_minutes,
        COUNT(DISTINCT m.match_id)  AS matches_played,
        AVG(CASE WHEN s.score = 'NaN'::double precision
                 THEN NULL ELSE s.score END) AS avg_score,
        -- DOMINANT (najwięcej minut) — fallback
        (ARRAY_AGG(m.club_id ORDER BY m.minutes DESC NULLS LAST))[1] AS dominant_club_id,
        (ARRAY_AGG(m.team_id ORDER BY m.minutes DESC NULLS LAST))[1] AS dominant_team_id,
        -- LAST (chronologicznie) — preferred dla obecnego sezonu
        (ARRAY_AGG(m.club_id ORDER BY m.match_date DESC NULLS LAST))[1] AS last_club_id,
        (ARRAY_AGG(m.team_id ORDER BY m.match_date DESC NULLS LAST))[1] AS last_team_id,
        MIN(m.match_date) AS first_match_date,
        MAX(m.match_date) AS last_match_date
    FROM pm_player_match_stats m
    JOIN active_candidates ac ON m.player_id = ac.player_id
    JOIN pm_player_match_score s
        ON m.match_id  = s.match_id
       AND m.player_id = s.player_id
    JOIN players p ON m.player_id = p._id
    JOIN tracked_leagues tl ON m.league_id = tl._id
    WHERE m.is_keeper = false
      AND m.minutes > 0
    GROUP BY m.player_id, p.firstname, p.lastname, m.season_id, m.league_id
)
SELECT
    h.player_id,
    h.player_name,
    h.season_id,
    h.league_id,
    l.name AS league_name,
    CASE h.league_id
        WHEN '337bb869-0b42-484f-8eca-0c8842a13ec9' THEN 13
        WHEN '50e40483-e8dc-4e4b-9f58-a83f93a54d9a' THEN 12
        WHEN '5f26d625-e72e-4aa5-9ffe-451025c18e3a' THEN 11
        WHEN '5cc45e5f-744b-428c-b8af-cdefca38de29' THEN 10
        WHEN 'c164ca31-22e4-43fc-9e30-4f3bcc2b7d72' THEN 9
        WHEN 'a0583713-115c-4aa5-90f2-140f6eaece15' THEN 8
        WHEN 'c5afdf4b-b449-4ef3-acf5-dded47fc5f58' THEN 7
        WHEN '63d04023-727a-4c0c-a8c6-4154fe1104b7' THEN 6
        WHEN 'b7d2c55b-e2af-44e2-9df2-3f6e05dc1768' THEN 5
        WHEN '895016b3-4fa6-4a68-aa41-5035f9ebef8e' THEN 4
        WHEN 'bf74d613-4cc6-4115-ad03-fac139dee351' THEN 9
        WHEN '8e70e715-3f0f-4481-a01d-51fb7b9aee90' THEN 9
        WHEN '279a6c2b-0504-4be3-9386-3c1ca785d11d' THEN 8
        WHEN '8104ee44-740c-4f6c-8fc3-3bbcf2b3b0e7' THEN 7
        WHEN '436dc4c6-bc94-4d30-ae92-1113d6d4eee3' THEN 5
        WHEN '5b788871-3d38-4073-9500-fcfa4d1b4270' THEN 5
        WHEN 'f19d92f4-14f7-45ab-884f-90da0d03f4a0' THEN 6
        WHEN '823a45df-052b-4cd5-a060-32ed52921992' THEN 4
        WHEN '75b51f36-93fd-49cb-86d3-6086dc88081b' THEN 4
        WHEN '317d1eb3-4873-4749-91b5-edb2d0cd4375' THEN 3
        WHEN 'adf4ca7f-46ef-4aff-a7a0-3e7cc614c59d' THEN 3
        WHEN '7c5a509a-2dac-46a7-9a37-54d48719758b' THEN 2
        WHEN '9d41a9e1-aa66-4e2c-9f33-6f4b01139837' THEN 2
        WHEN '811e1235-dc60-4db3-bf68-ee9b43d8370c' THEN 1
        WHEN 'bf404c9a-f13c-4835-885a-43ba3774850c' THEN 1
        ELSE NULL
    END AS league_level,
    CASE WHEN h.league_id IN (
        'bf74d613-4cc6-4115-ad03-fac139dee351', '8e70e715-3f0f-4481-a01d-51fb7b9aee90',
        '279a6c2b-0504-4be3-9386-3c1ca785d11d', '8104ee44-740c-4f6c-8fc3-3bbcf2b3b0e7',
        '436dc4c6-bc94-4d30-ae92-1113d6d4eee3', '5b788871-3d38-4073-9500-fcfa4d1b4270',
        'f19d92f4-14f7-45ab-884f-90da0d03f4a0', '823a45df-052b-4cd5-a060-32ed52921992',
        '75b51f36-93fd-49cb-86d3-6086dc88081b', '317d1eb3-4873-4749-91b5-edb2d0cd4375',
        'adf4ca7f-46ef-4aff-a7a0-3e7cc614c59d', '7c5a509a-2dac-46a7-9a37-54d48719758b',
        '9d41a9e1-aa66-4e2c-9f33-6f4b01139837', '811e1235-dc60-4db3-bf68-ee9b43d8370c',
        'bf404c9a-f13c-4835-885a-43ba3774850c'
    ) THEN true ELSE false END AS is_junior_league,
    h.age_in_season,
    h.total_minutes,
    h.matches_played,
    ROUND(h.avg_score::numeric, 4) AS avg_score,
    -- Dominant (fallback)
    h.dominant_club_id,
    c1.name AS club_name_dominant,
    h.dominant_team_id,
    t1.name AS team_name_dominant,
    -- Last chronologicznie (preferred)
    h.last_club_id,
    c2.name AS club_name_last,
    h.last_team_id,
    t2.name AS team_name_last,
    h.first_match_date,
    h.last_match_date
FROM candidate_history h
JOIN leagues l ON h.league_id = l._id
LEFT JOIN clubs c1 ON h.dominant_club_id = c1._id
LEFT JOIN teams t1 ON h.dominant_team_id = t1._id
LEFT JOIN clubs c2 ON h.last_club_id = c2._id
LEFT JOIN teams t2 ON h.last_team_id = t2._id
ORDER BY h.player_id, h.age_in_season, h.league_id;
