/*
	Table creation scripts
*/
CREATE TABLE game_lists (
	game_list_id SERIAL primary key,
	game_list_name VARCHAR(400),
	channel_id NUMERIC,
	active bool default true,
	server_name VARCHAR(400),
	server_id NUMERIC,
	started_date TIMESTAMP default CURRENT_TIMESTAMP,
	modified_date TIMESTAMP default CURRENT_TIMESTAMP
);

CREATE TABLE games (
	game_id SERIAL primary key,
	game_list_id INT references game_lists(game_list_id),
	game_url varchar(1000),
	user_name varchar(100),
	active bool default true,
	added_date TIMESTAMP default CURRENT_TIMESTAMP,
	modified_date TIMESTAMP default CURRENT_TIMESTAMP
);

/*
	Contraints
*/
CREATE UNIQUE INDEX idx_unique_inactive_game_lists
ON game_lists (server_id, channel_id)
WHERE active = true;

ALTER TABLE game_lists
ADD CONSTRAINT chk_inactive_game_lists
CHECK (
    (active = false) OR 
    (active = true AND (channel_id, server_id) IS DISTINCT FROM (NULL, NULL))
);

CREATE UNIQUE INDEX idx_unique_inactive_games
ON games (user_name, game_url, game_list_id)
WHERE active = true;

ALTER TABLE games
ADD CONSTRAINT chk_inactive_games
CHECK (
    (active = false) OR 
    (active = true AND (user_name, game_url, game_list_id) IS DISTINCT FROM (NULL, NULL, NULL))
);

/*
	Triggers and functions
*/
-- Update modified date on update
CREATE OR REPLACE
FUNCTION update_modified_date()
RETURNS trigger AS $$
BEGIN
	IF new.* IS DISTINCT FROM old.* THEN
		new.modified_date := NOW();
	END IF;

	RETURN new;
END;
$$ LANGUAGE plpgsql;

-- Run update modified function on games update
CREATE TRIGGER update_games_trigger
BEFORE UPDATE ON games 
	FOR EACH ROW WHEN (
		new.* IS DISTINCT FROM old.*
	)
EXECUTE FUNCTION update_modified_date();

-- Run update modified function on game_lists update
CREATE TRIGGER update_game_lists_trigger
BEFORE UPDATE ON game_lists 
	FOR EACH ROW WHEN (
		new.* IS DISTINCT FROM old.*
	)
EXECUTE FUNCTION update_modified_date();

-- Update active flag to false for all games with the same game_list_id
CREATE OR REPLACE FUNCTION update_games_active()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.active = false THEN
        UPDATE games
        SET active = false
        WHERE game_list_id = OLD.game_list_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- When game_lists.active is set to false run the update games active function
CREATE TRIGGER update_games_trigger
AFTER UPDATE ON game_lists
FOR EACH ROW WHEN (new.active IS false)
EXECUTE FUNCTION update_games_active();

/*
	Create database users and grant privs
*/
CREATE USER discord_bot WITH PASSWORD 'secretpassword';
--ALTER USER discord_bot VALID UNTIL 'yesterday';
--ALTER USER discord_bot VALID UNTIL 'infinity'; Run after updating password and update .env
GRANT CONNECT ON DATABASE postgres TO discord_bot;
GRANT SELECT, INSERT, UPDATE ON games TO discord_bot;
GRANT SELECT, INSERT, UPDATE ON game_lists TO discord_bot;

GRANT USAGE ON SEQUENCE game_lists_game_list_id_seq TO PUBLIC;
GRANT USAGE ON SEQUENCE games_game_id_seq TO PUBLIC;