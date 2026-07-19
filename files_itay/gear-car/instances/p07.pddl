(define (problem car_linear_gears_p07)
    (:domain car_linear_gears_numeric)

    (:objects
        g1 g2 g3 - gear
    )

    (:init
        (current_gear g1)
        (gear_next g1 g2)
        (gear_next g2 g3)

        (= (d) 0)
        (= (v) 0)
        (= (a) 0)

        (= (max_acceleration) 2)
        (= (min_acceleration) -1)
        (= (max_speed) 6)
        (= (acc_step) 1)

        (= (fuel) 513)
        (= (fuel_used) 0)
        (= (elapsed_time) 0)
        (= (cost) 0)
        (= (alpha) 35466)
        (= (beta) 69)

        (= (shift_count) 0)

        (= (gear_v_min g1) 0)
        (= (gear_v_max g1) 2)
        (= (gear_min_acceleration g1) -1)
        (= (gear_max_acceleration g1) 2)
        (= (gear_fuel_aligned g1) 11)
        (= (gear_fuel_under g1) 18)
        (= (gear_fuel_over g1) 18)

        (= (gear_v_min g2) 2)
        (= (gear_v_max g2) 4)
        (= (gear_min_acceleration g2) -1)
        (= (gear_max_acceleration g2) 1)
        (= (gear_fuel_aligned g2) 9)
        (= (gear_fuel_under g2) 17)
        (= (gear_fuel_over g2) 15)

        (= (gear_v_min g3) 4)
        (= (gear_v_max g3) 6)
        (= (gear_min_acceleration g3) -1)
        (= (gear_max_acceleration g3) 0)
        (= (gear_fuel_aligned g3) 8)
        (= (gear_fuel_under g3) 17)
        (= (gear_fuel_over g3) 13)
    )

    (:goal
        (and
            (>= (d) 540)
            (<= (d) 542)
            (current_gear g1)
            (= (v) 0)
            (= (a) 0)
            (>= (fuel) 0)
            (> (fuel_used) 0)
        )
    )

    (:metric minimize (cost))
)
