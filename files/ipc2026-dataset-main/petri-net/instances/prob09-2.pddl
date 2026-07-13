;;Anonymous
(define (problem prob09-2)
  (:domain petri-net)
  (:objects
     s0 a1 a2 a3 b1 b2 b3 c1 c2 c3 d1 d2 g - place
  )

  (:init
    (source s0)

    (one-to-one s0 a1)
    (one-to-one s0 b1)
    (one-to-one s0 c1)
    

    (one-to-one a1 a2)
    (one-to-one b1 b2)
    (one-to-one c1 c2)
    
    (one-to-one a2 a3)
    (one-to-one b2 b3)
    (one-to-one c2 c3)
    
    (one-to-one a3 d1)
    (one-to-one b3 d1)
    (one-to-one c3 d1)
    
    (three-to-one a3 b3 c3 d2)
    (two-to-one d1 d2 g)
        
    (= (value s0) 0)
    (= (value a1) 0)
    (= (value a2) 0)
    (= (value a3) 0)
    (= (value b1) 0)
    (= (value b2) 0)
    (= (value b3) 0)
    (= (value c1) 0)
    (= (value c2) 0)
    (= (value c3) 0)

    (= (value d1) 0)
    (= (value d2) 0)
    
    (= (value g) 0)
    (= (cost) 0)
  )

  (:goal (and 
         (= 4 (value g))
         (= 1 (+ (+ (value a3) (value b3)) (value c3))))
  )

  (:metric minimize (cost))
  
)
