(define (problem p12)
    (:domain ztalloc-sum)

    (:objects
        r1 r2 r3 r4 r5 - register
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
        (normal r4)
        (= (value r4) 1)
        (= (work-value r4) 0)
        (normal r5)
        (= (value r5) 1)
        (= (work-value r5) 0)
        (= (total-cost) 0)
    )

    (:goal
        (and
            (= (+ (+ (+ (+ (value r1) (value r2)) (value r3)) (value r4)) (value r5)) 4269)
            (free)
            (normal r1)
            (= (work-value r1) 0)
            (normal r2)
            (= (work-value r2) 0)
            (normal r3)
            (= (work-value r3) 0)
            (normal r4)
            (= (work-value r4) 0)
            (normal r5)
            (= (work-value r5) 0)
        )
    )

    (:metric minimize (total-cost))
)
