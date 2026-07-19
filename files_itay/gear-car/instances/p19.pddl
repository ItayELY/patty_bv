(define (problem car_linear_gears_p19)
    (:domain car_linear_gears_numeric)

    (:objects
        g1 g2 g3 g4 g5 - gear
    )

    (:init
        (current_gear g1)
        (gear_next g1 g2)
        (gear_next g2 g3)
        (gear_next g3 g4)
        (gear_next g4 g5)

        (= (d) 0)
        (= (v) 0)
        (= (a) 0)

        (= (max_acceleration) 2)
        (= (min_acceleration) -1)
        (= (max_speed) 10)
        (= (acc_step) 1)

        (= (fuel) 902)
        (= (fuel_used) 0)
        (= (elapsed_time) 0)
        (= (cost) 0)
        (= (alpha) 143577)
        (= (beta) 159)

        (= (shift_count) 0)

        (= (gear_v_min g1) 0)
        (= (gear_v_max g1) 2)
        (= (gear_min_acceleration g1) -1)
        (= (gear_max_acceleration g1) 2)
        (= (gear_fuel_aligned g1) 11)
        (= (gear_fuel_under g1) 18)
        (= (gear_fuel_over g1) 20)

        (= (gear_v_min g2) 2)
        (= (gear_v_max g2) 4)
        (= (gear_min_acceleration g2) -1)
        (= (gear_max_acceleration g2) 1)
        (= (gear_fuel_aligned g2) 9)
        (= (gear_fuel_under g2) 17)
        (= (gear_fuel_over g2) 17)

        (= (gear_v_min g3) 4)
        (= (gear_v_max g3) 6)
        (= (gear_min_acceleration g3) -1)
        (= (gear_max_acceleration g3) 1)
        (= (gear_fuel_aligned g3) 8)
        (= (gear_fuel_under g3) 17)
        (= (gear_fuel_over g3) 15)

        (= (gear_v_min g4) 6)
        (= (gear_v_max g4) 8)
        (= (gear_min_acceleration g4) -1)
        (= (gear_max_acceleration g4) 1)
        (= (gear_fuel_aligned g4) 7)
        (= (gear_fuel_under g4) 17)
        (= (gear_fuel_over g4) 13)

        (= (gear_v_min g5) 8)
        (= (gear_v_max g5) 10)
        (= (gear_min_acceleration g5) -1)
        (= (gear_max_acceleration g5) 0)
        (= (gear_fuel_aligned g5) 6)
        (= (gear_fuel_under g5) 17)
        (= (gear_fuel_over g5) 11)
    )

    (:goal
        (and
            (>= (d) 2160)
            (<= (d) 2162)
            (current_gear g1)
            (= (v) 0)
            (= (a) 0)
            (>= (fuel) 0)
            (> (fuel_used) 0)
        )
    )

    (:metric minimize (cost))
)
