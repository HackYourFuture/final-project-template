-- An empty mart passes every column test, which is exactly why it needs its
-- own check. A silent zero-row build is the failure students hit most often.
select 1 as problem
from (select count(*) as n from {{ ref('fct_postings') }}) counted
where counted.n = 0
