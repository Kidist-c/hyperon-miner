!(import! &self experiments/utils/common-utils)
!(import! &db experiments/data/ugly_man_sodaDrinker)

!(let $pattern
    (, (Inheritance $x human)
       (Inheritance $x man))
    (let $matches
        (collapse (match &db $pattern $pattern))
        (println! "ACTUAL MATCHES:")
        (println! $matches)
        (println! "MATCH COUNT:")
        (println! (tuple-count $matches))
    )
)