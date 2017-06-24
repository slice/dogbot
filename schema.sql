CREATE TABLE IF NOT EXISTS command_statistics (
  command_name text,
  times_used int,
  last_used timestamp without time zone
);

CREATE TABLE IF NOT EXISTS rps_exclusions (
  user_id bigint
);

CREATE TABLE IF NOT EXISTS censorship (
  guild_id bigint,
  enabled text[],
  exceptions bigint[]
);

CREATE TABLE IF NOT EXISTS censorship_punishments (
  guild_id bigint,
  censorship_type text,
  punishment text,

  PRIMARY KEY(guild_id, censorship_type)
);

CREATE TABLE IF NOT EXISTS exhausted_reddit_posts (
  guild_id bigint,
  post_id text
);

CREATE TABLE IF NOT EXISTS blacklisted_guilds (
  guild_id bigint primary key
);

CREATE TABLE IF NOT EXISTS reminders (
  id serial primary key,
  author_id bigint,
  channel_id bigint,
  note text,
  due timestamp without time zone
);

CREATE TABLE IF NOT EXISTS prefixes (
  guild_id bigint,
  prefix varchar(140) primary key
);

CREATE TABLE IF NOT EXISTS reddit_feeds (
  guild_id bigint,
  channel_id bigint,
  subreddit text
);

CREATE TABLE IF NOT EXISTS tags (
  name text,
  guild_id bigint,
  creator_id bigint,
  value text,
  uses int,
  created_at timestamp without time zone
);
