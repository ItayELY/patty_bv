;;Anonymous
(define (problem prob06-3)
  (:domain petri-net)
  (:objects
    s0 a1 a2 a3 a4 a5 a6 a7 a8 b1 b2 b3 b4 b5 b6 b7 b8 c1 c2 c3 c4 c5 c6 c7 c8 g - place
  )

  (:init
    (source s0)
    
    (one-to-one s0 a1)
    (one-to-one s0 b1)
    (one-to-one s0 c1)
    
    
    (one-to-one a1 a2)
    (one-to-one a2 a3)
    (one-to-one a3 a4)
    
    
    (one-to-one a4 a5)
    (one-to-one a4 a6)
    (one-to-one a4 a7)
   

    (one-to-two a5 a6 a4)
    (one-to-two a6 a7 a4)
    (one-to-two a7 a5 a4)
    
    (three-to-one a5 a6 a7 a8)
    
    (one-to-one b1 b2)
    (one-to-one b2 b3)
    (one-to-one b3 b4)
    
    
    (one-to-one b4 b5)
    (one-to-one b4 b6)
    (one-to-one b4 b7)
   

    (one-to-two b5 b6 b4)
    (one-to-two b6 b7 b4)
    (one-to-two b7 b5 b4)
    
    (three-to-one b5 b6 b7 b8)
    
    (one-to-one c1 c2)
    (one-to-one c2 c3)
    (one-to-one c3 c4)
    
    
    (one-to-one c4 c5)
    (one-to-one c4 c6)
    (one-to-one c4 c7)
   

    (one-to-two c5 c6 c4)
    (one-to-two c6 c7 c4)
    (one-to-two c7 c5 c4)
    
    (three-to-one c5 c6 c7 c8)
    
    (three-to-one a7 b7 c7 g)
    (three-to-one a8 b8 c8 g)
    

    (= (value s0) 0)    
    (= (value a1) 0)
    (= (value a2) 0)
    (= (value a3) 0)
    (= (value a4) 0)
    (= (value a5) 0)
    (= (value a6) 0)
    (= (value a7) 0)
    (= (value a8) 0)
    (= (value b1) 0)
    (= (value b2) 0)
    (= (value b3) 0)
    (= (value b4) 0)
    (= (value b5) 0)
    (= (value b6) 0)
    (= (value b7) 0)
    (= (value b8) 0)
    (= (value c1) 0)
    (= (value c2) 0)
    (= (value c3) 0)
    (= (value c4) 0)
    (= (value c5) 0)
    (= (value c6) 0)
    (= (value c7) 0)
    (= (value c8) 0)
    (= (value g) 0)
    (= (cost) 0)
  )

  (:goal (and 
         (= 3 (value g))
         (= (value a4) 1)
         (= (value b4) 1)
         (= (value c4) 1)
         
         )
  )

  (:metric minimize (cost))
  
 )
