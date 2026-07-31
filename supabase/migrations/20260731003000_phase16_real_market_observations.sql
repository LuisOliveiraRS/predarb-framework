begin;

create table if not exists
    public.real_market_observations (
        id bigint
            generated always as identity
            primary key,

        observed_at timestamptz
            not null,

        connector_id text
            not null,

        market_id text
            not null,

        title text,

        source_url text,

        yes_ask numeric(18, 10),

        no_ask numeric(18, 10),

        total_cost numeric(18, 10)
            not null,

        gross_edge numeric(18, 10)
            not null,

        conservative_edge numeric(18, 10)
            not null,

        status text
            not null
            check (
                status in (
                    'PROFITABLE',
                    'NEAR_OPPORTUNITY',
                    'NORMAL'
                )
            ),

        created_at timestamptz
            not null
            default now(),

        constraint real_market_observations_unique
            unique (
                connector_id,
                market_id,
                observed_at
            )
    );

create index if not exists
    real_market_observations_market_time_idx
on public.real_market_observations (
    connector_id,
    market_id,
    observed_at desc
);

create index if not exists
    real_market_observations_time_idx
on public.real_market_observations (
    observed_at desc
);

create index if not exists
    real_market_observations_status_edge_idx
on public.real_market_observations (
    status,
    gross_edge desc
);

alter table public.real_market_observations
    enable row level security;

revoke all
    on table public.real_market_observations
    from anon, authenticated;

comment on table
    public.real_market_observations
is
    'Read-only market observations collected by '
    'the PredArb opportunity monitor.';

comment on column
    public.real_market_observations.gross_edge
is
    'Observed edge before the configured fee buffer.';

comment on column
    public.real_market_observations.conservative_edge
is
    'Observed edge after the configured fee buffer.';

commit;
