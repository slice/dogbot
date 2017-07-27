CREATE TABLE command_statistics (
  command_name text,
  times_used int,
  last_used timestamp without time zone
);

CREATE TABLE rps_exclusions (
  user_id bigint
);

CREATE TABLE censorship (
  guild_id bigint,
  enabled text[],
  exceptions bigint[]
);

CREATE TABLE censorship_punishments (
  guild_id bigint,
  censorship_type text,
  punishment text,

  PRIMARY KEY(guild_id, censorship_type)
);

CREATE TABLE exhausted_reddit_posts (
  guild_id bigint,
  post_id text
);

CREATE TABLE blacklisted_guilds (
  guild_id bigint primary key
);

CREATE TABLE music_guilds (
  guild_id bigint primary key
);

CREATE TABLE reminders (
  id serial primary key,
  author_id bigint,
  channel_id bigint,
  note text,
  due timestamp without time zone
);

CREATE TABLE prefixes (
  guild_id bigint,
  prefix varchar(140) primary key
);

CREATE TABLE reddit_feeds (
  guild_id bigint,
  channel_id bigint,
  subreddit text
);

CREATE TABLE tags (
  name text,
  guild_id bigint,
  creator_id bigint,
  value text,
  uses int,
  created_at timestamp without time zone
);

CREATE TABLE autoroles (
  guild_id bigint,
  type text,
  roles bigint[],

  PRIMARY KEY (guild_id, type)
);

CREATE TABLE globalbans (
  user_id bigint primary key,
  reason text,
  created_at timestamp without time zone
);

CREATE TABLE users (
  id bigint primary key,
  is_global_admin boolean
);

CREATE TABLE guilds (
  id bigint primary key,
  owner bigint references users(id)
);

CREATE TABLE profile_descriptions (
  id bigint primary key,
  description text,
  color int
);

CREATE TABLE messages (
  message_id bigint primary key,
  guild_id bigint,
  channel_id bigint,
  author_id bigint,
  created_at timestamp without time zone,

  original_content text,
  new_content text,

  attachments jsonb,

  deleted boolean,
  edited boolean,
  deleted_at timestamp without time zone,
  edited_at timestamp without time zone
);
