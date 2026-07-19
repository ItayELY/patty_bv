;;Anonymous
(define (problem prob07-1)
  (:domain petri-net)
  (:objects
    s0 p1 p2 p3 p4 p5 p6 p7 p8 q1 q2 q3 q4 q5 q6 q7 q8 g - place
  )

  (:init
    (source s0)
    
    (sink p2)
    (sink q2)
    
    (one-to-one s0 p1)
    (one-to-one s0 q1)
      
    (one-to-one p1 p2)
    (one-to-one p1 p3)
    (one-to-one p1 p4)
    (one-to-two p1 p2 p4)
    (one-to-two p1 p2 p3)
    
    (two-to-one p1 p4 p5)
    (two-to-one p1 p3 p5)
    
    (one-to-one p5 p6)
    (one-to-one p5 p7)
    (one-to-one p6 p8)
    (one-to-two p8 p8 p8)
    
    (one-to-one q1 q2)
    (one-to-one q1 q3)
    (one-to-one q1 q4)
    (one-to-two q1 q2 q4)
    (one-to-two q1 q2 q3)
    
    (two-to-one q1 q4 q5)
    (two-to-one q1 q3 q5)
    
    (one-to-one q5 q6)
    (one-to-one q5 q7)
    (one-to-one q6 q8)
    (one-to-two q8 q8 q8)
    
    (two-to-one p8 q8 g)

    (= (value s0) 0)    
    (= (value p1) 0)
    (= (value p2) 0)
    (= (value p3) 0)
    (= (value p4) 0)
    (= (value p5) 0)
    (= (value p6) 0)
    (= (value p7) 0)
    (= (value p8) 0)
    (= (value q1) 0)
    (= (value q2) 0)
    (= (value q3) 0)
    (= (value q4) 0)
    (= (value q5) 0)
    (= (value q6) 0)
    (= (value q7) 0)
    (= (value q8) 0)
    (= (value g) 0)    
    (= (cost) 0)
  )

  (:goal (and 
         (= 3 (value g))
         (= 2 (value p5))
         (= 2 (value q5))
         (= (value p2) 0)
         (= (value p3) 0)
         (= (value p4) 0)
         (= (value q2) 0)
         (= (value q3) 0)
         (= (value q4) 0)
         )
  )

  (:metric minimize (cost))
  
)
