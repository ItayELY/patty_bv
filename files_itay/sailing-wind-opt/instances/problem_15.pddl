

(define (problem test) (:domain sailing-wind)
(:objects 
    b0 - boat
    p0 - person
)

(:init
    (= (vmax_0 b0) 0)
	(= (vmax_15 b0) 0.17)
	(= (vmax_30 b0) 0.3)
	(= (vmax_45 b0) 0.45)
	(= (vmax_60 b0) 0.65)
	(= (vmax_75 b0) 1)
	(= (vmax_90 b0) 1.49)
	(= (vmax_105 b0) 1.44)
	(= (vmax_120 b0) 1.37)
	(= (vmax_135 b0) 1.26)
	(= (vmax_150 b0) 1.12)
	(= (vmax_165 b0) 0.96)
	(= (vmax_180 b0) 0.8)
	(= (x b0) 0)
	(= (y b0) 0)
	(= (r b0) 0.5)
	(= (v b0) 0)
	(= (sailing-angle b0) 0)
	(= (x p0) 11.0)
	(= (y p0) 21.5)
)

(:goal (and
    (saved p0)
))

;un-comment the following line if metric is needed
;(:metric minimize (???))
)
