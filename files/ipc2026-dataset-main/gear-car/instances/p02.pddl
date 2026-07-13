(define (problem car_linear_gears_p02)
    (:domain car_linear_gears_numeric)

    (:objects
        g1 g2 - gear
    )

    (:init
        (current_gear g1)
        (gear_next g1 g2)

        (= (d) 0)
        (= (v) 0)
        (= (a) 0)

        (= (max_acceleration) 2)
        (= (min_acceleration) -1)
        (= (max_speed) 4)
        (= (acc_step) 1)

        (= (fuel) 450)
        (= (fuel_used) 0)
        (= (elapsed_time) 0)
        (= (cost) 0)
        (= (alpha) 23903)
        (= (beta) 53)

        (= (shift_count) 0)

        (= (gear_v_min g1) 0)
        (= (gear_v_max g1) 2)
        (= (gear_min_acceleration g1) -1)
        (= (gear_max_acceleration g1) 2)
        (= (gear_fuel_aligned g1) 11)
        (= (gear_fuel_under g1) 18)
        (= (gear_fuel_over g1) 17)

        (= (gear_v_min g2) 2)
        (= (gear_v_max g2) 4)
        (= (gear_min_acceleration g2) -1)
        (= (gear_max_acceleration g2) 0)
        (= (gear_fuel_aligned g2) 9)
        (= (gear_fuel_under g2) 17)
        (= (gear_fuel_over g2) 14)
    )

    (:goal
        (and
            (>= (d) 290)
            (<= (d) 292)
            (current_gear g1)
            (= (v) 0)
            (= (a) 0)
            (>= (fuel) 0)
            (> (fuel_used) 0)
        )
    )

    (:metric minimize (cost))
)
