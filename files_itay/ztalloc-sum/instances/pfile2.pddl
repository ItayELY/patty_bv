(define (problem p2)
    (:domain ztalloc-sum)

    (:objects
        r1 r2 r3 - register
    )

    (:init
        (free)
        (normal r1)
        (= (value r1) 1)
        (= (work-value r1) 0)
        (normal r2)
        (= (value r2) 1)
        (= (work-value r2) 0)
        (normal r3)
        (= (value r3) 1)
        (= (work-value r3) 0)
        (= (total-cost) 0)
    )

    (:goal
        (and
            (= (+ (+ (value r1) (value r2)) (value r3)) 233)
            (free)
            (normal r1)
            (= (work-value r1) 0)
            (normal r2)
            (= (work-value r2) 0)
            (normal r3)
            (= (work-value r3) 0)
        )
    )

    (:metric minimize (total-cost))
)
