
(define (problem p1)
    (:domain coins)

    (:objects
        c1 c2 c3 c4 c5 - coin
    )

    (:init
        (= (denomination c1) 1)
        (= (denomination c2) 2)
        (= (denomination c3) 3)
        (= (denomination c4) 5)
        (= (denomination c5) 7)

        (= (denomination-penalty c1) 1)
        (= (denomination-penalty c2) 1)
        (= (denomination-penalty c3) 1)
        (= (denomination-penalty c4) 1)
        (= (denomination-penalty c5) 1)

        (no-coin-update c1)
        (no-coin-update c2)
        (no-coin-update c3)
        (no-coin-update c4)
        (no-coin-update c5)

        (= (current-value) 0)
        (= (coin-count) 0)
        (= (penalty) 0)
    )

    (:goal
        (and
            (= (current-value) 29)
            (= (penalty) 0)
        )
    )

    (:metric minimize (coin-count))

)
