create table users
(
    id   UUID not null constraint users_pk primary key,
    email text NOT NULL
);
