; Solution sequence: left up left down right up down left up right down right up left down left up left down right up left up left up up
(define (problem pfile26)
    (:domain twenty-forty-eight)

    ; Initial board (0 = empty):
    ;
    ;   32 | 0 | 128 | 2048
    ;   1024 | 64 | 128 | 1024
    ;   1024 | 0 | 512 | 32
    ;   1024 | 64 | 64 | 1024

    ; Goal:
    ;
    ;   8192 | 0 | 0 | 0
    ;   0 | 0 | 0 | 0
    ;   0 | 0 | 0 | 0
    ;   0 | 0 | 0 | 0

    (:init

        ;; ---- pos-at: (direction, row/col, index) → position ----
        ;; i1 = closest to target edge, i4 = farthest

        ; L — target edge is left; iterate over rows
        (pos-at L top i1 p11) (pos-at L top i2 p12) (pos-at L top i3 p13) (pos-at L top i4 p14)
        (pos-at L midtop i1 p21) (pos-at L midtop i2 p22) (pos-at L midtop i3 p23) (pos-at L midtop i4 p24)
        (pos-at L midbot i1 p31) (pos-at L midbot i2 p32) (pos-at L midbot i3 p33) (pos-at L midbot i4 p34)
        (pos-at L bot i1 p41) (pos-at L bot i2 p42) (pos-at L bot i3 p43) (pos-at L bot i4 p44)

        ; R — target edge is right; iterate over rows
        (pos-at R top i1 p14) (pos-at R top i2 p13) (pos-at R top i3 p12) (pos-at R top i4 p11)
        (pos-at R midtop i1 p24) (pos-at R midtop i2 p23) (pos-at R midtop i3 p22) (pos-at R midtop i4 p21)
        (pos-at R midbot i1 p34) (pos-at R midbot i2 p33) (pos-at R midbot i3 p32) (pos-at R midbot i4 p31)
        (pos-at R bot i1 p44) (pos-at R bot i2 p43) (pos-at R bot i3 p42) (pos-at R bot i4 p41)

        ; U — target edge is top; iterate over columns
        (pos-at U left i1 p11) (pos-at U left i2 p21) (pos-at U left i3 p31) (pos-at U left i4 p41)
        (pos-at U midleft i1 p12) (pos-at U midleft i2 p22) (pos-at U midleft i3 p32) (pos-at U midleft i4 p42)
        (pos-at U midright i1 p13) (pos-at U midright i2 p23) (pos-at U midright i3 p33) (pos-at U midright i4 p43)
        (pos-at U right i1 p14) (pos-at U right i2 p24) (pos-at U right i3 p34) (pos-at U right i4 p44)

        ; D — target edge is bottom; iterate over columns
        (pos-at D left i1 p41) (pos-at D left i2 p31) (pos-at D left i3 p21) (pos-at D left i4 p11)
        (pos-at D midleft i1 p42) (pos-at D midleft i2 p32) (pos-at D midleft i3 p22) (pos-at D midleft i4 p12)
        (pos-at D midright i1 p43) (pos-at D midright i2 p33) (pos-at D midright i3 p23) (pos-at D midright i4 p13)
        (pos-at D right i1 p44) (pos-at D right i2 p34) (pos-at D right i3 p24) (pos-at D right i4 p14)

        ;; ---- Row/col iteration order ----
        (next L top midtop) (next L midtop midbot) (next L midbot bot) (next L bot done)
        (next R top midtop) (next R midtop midbot) (next R midbot bot) (next R bot done)
        (next U left midleft) (next U midleft midright) (next U midright right) (next U right done)
        (next D left midleft) (next D midleft midright) (next D midright right) (next D right done)

        ;; ---- Start status ----
        (start-status L top)
        (start-status R top)
        (start-status U left)
        (start-status D left)

        ;; ---- Index chain for combine pair iteration ----
        (next-idx i1 i2) (next-idx i2 i3) (next-idx i3 i4)

        ;; ---- Game state ----
        (free-to-play)

        ;; ---- Tile values ----
        (= (value p11) 32) (= (value p12) 0) (= (value p13) 128) (= (value p14) 2048)
        (= (value p21) 1024) (= (value p22) 64) (= (value p23) 128) (= (value p24) 1024)
        (= (value p31) 1024) (= (value p32) 0) (= (value p33) 512) (= (value p34) 32)
        (= (value p41) 1024) (= (value p42) 64) (= (value p43) 64) (= (value p44) 1024)
    )

    (:goal (and
        (= (value p11) 8192) (= (value p12) 0) (= (value p13) 0) (= (value p14) 0)
        (= (value p21) 0) (= (value p22) 0) (= (value p23) 0) (= (value p24) 0)
        (= (value p31) 0) (= (value p32) 0) (= (value p33) 0) (= (value p34) 0)
        (= (value p41) 0) (= (value p42) 0) (= (value p43) 0) (= (value p44) 0)
    ))

)
