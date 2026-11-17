!(import! &self experiments/utils/common-utils)
!(import! &db experiments/data/ugly_man_sodaDrinker)

!(let $pattern
    (, (Inheritance $x ugly)
       (Inheritance $x sodaDrinker))
    (let $matches
        (collapse (match &db $pattern $pattern))
        (println! (tuple-count $matches))
    )
)