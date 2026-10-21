import unittest
from tests.test_food_economy import quiet,population
from systems.economy import food_upkeep

class PersonalUpkeepTests(unittest.TestCase):
    def test_completed_boundary_and_idempotence(self):
        e=quiet();c=population(e,1);c.reserves=5
        for t in range(1,100):e.economy.tick(t)
        self.assertEqual(c.reserves,5)
        e.economy.tick(100);e.economy.tick(100)
        self.assertEqual(c.reserves,4)
        e.economy.tick(199);self.assertEqual(c.reserves,4)
        e.economy.tick(200);self.assertEqual(c.reserves,3)
    def test_personal_first_partial_and_shared_fallback(self):
        for cargo,shared in ((1,0),(.5,.5),(0,1)):
            with self.subTest(cargo=cargo):
                e=quiet();c=population(e,1);a=e.world.ants[0];a.cargo=cargo;c.reserves=5
                before=e.food.accounting()['inventory'];e.economy.tick(100)
                self.assertEqual(a.cargo,0);self.assertEqual(c.reserves,5-shared)
                self.assertEqual(c.upkeep_personal_half,2*cargo)
                self.assertEqual(c.upkeep_shared_half,2*shared)
                self.assertEqual(c.upkeep_spent_half,2)
                self.assertEqual(e.food.accounting()['inventory'],before-1)
    def test_shortage_preserves_signed_debt_and_penalty(self):
        e=quiet();c=population(e,1);e.world.ants[0].cargo=.5;c.reserves=0
        e.economy.tick(100);self.assertEqual(c.reserves,-.5);self.assertEqual(c.queen.hp,50)
        e.economy.tick(101);self.assertEqual(c.queen.hp,49)
    def test_progressive_cost_and_stable_identity(self):
        e=quiet();c=population(e,51);a=e.world.ants[-1];a.cargo=1.5
        e.world.ants.reverse();e.economy.tick(100)
        self.assertEqual(c.reserves,-food_upkeep(51)+1.5)
        self.assertEqual(a.cargo,0)
    def test_soldier_ration_capacity_no_delivery_and_one_action(self):
        e=quiet();a=e.world.ants[0];a.kind='soldier';s=e.world.stations[0];a.position=s.position
        before=e.food.accounting()['inventory'];e.fsm.resolve_action(a,1);e.fsm.resolve_action(a,1)
        self.assertEqual(a.cargo,1);self.assertEqual(s.units,4)
        self.assertEqual(e.food.accounting()['inventory'],before)
        a.position=e.fsm.base_cells(a)[0];a.last_action=None;a.action_used=False
        e.fsm.resolve_action(a,2)
        self.assertEqual(a.cargo,1);self.assertEqual(e.world.colonies[0].reserves,0)
        e.economy.tick(100);self.assertEqual(a.cargo,0)
    def test_worker_transport_is_same_inventory_and_conserved(self):
        e=quiet();a=e.world.ants[0];a.position=e.world.stations[0].position
        self.assertEqual(e.food.accounting()['residual'],0)
        e.fsm.resolve_action(a,1);self.assertEqual(a.cargo,1)
        e.economy.tick(100)
        # Approved source-first settlement preserves this carrier's food.
        self.assertEqual(a.cargo,1);self.assertEqual(e.world.stations[0].units,3)
        self.assertEqual(e.food.accounting()['residual'],0)
    def test_soil_shares_soldier_capacity(self):
        e=quiet();a=e.world.ants[0];a.kind='soldier';a.soil_cargo=1;a.position=e.world.stations[0].position
        e.fsm.resolve_action(a,1);self.assertEqual(a.cargo,0)
    def test_dead_ants_do_not_pay(self):
        e=quiet();c=population(e,1);a=e.world.ants[0];a.hp=0;a.cargo=1
        e.economy.tick(100);self.assertEqual(a.cargo,1);self.assertEqual(c.last_upkeep,0)
