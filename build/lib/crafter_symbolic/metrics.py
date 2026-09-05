"""The 22-achievement Crafter metric; not average per-episode score."""
import math
import statistics

ACHIEVEMENTS = (
    'collect_coal', 'collect_diamond', 'collect_drink', 'collect_iron',
    'collect_sapling', 'collect_stone', 'collect_wood', 'defeat_skeleton',
    'defeat_zombie', 'eat_cow', 'eat_plant', 'make_iron_pickaxe', 'make_iron_sword',
    'make_stone_pickaxe', 'make_stone_sword', 'make_wood_pickaxe', 'make_wood_sword',
    'place_furnace', 'place_plant', 'place_stone', 'place_table', 'wake_up',
)


def summarize(rows):
    if not rows:
        raise ValueError('At least one completed episode is required')
    n = len(rows)
    counts = {a: sum(r['achievements'].get(a, 0) > 0 for r in rows) for a in ACHIEVEMENTS}
    rates = {a: 100 * count/n for a, count in counts.items()}
    score = math.expm1(sum(math.log1p(rates[a]) for a in ACHIEVEMENTS)/len(ACHIEVEMENTS))
    times = [r['first_diamond_step'] for r in rows if r['first_diamond_step'] is not None]
    return {
        'episodes': n, 'crafter_score': score,
        'diamond_successes': counts['collect_diamond'],
        'diamond_percent': rates['collect_diamond'],
        'achievement_episode_counts': counts, 'achievement_percent': rates,
        'mean_episode_steps': statistics.mean(r['steps'] for r in rows),
        'first_diamond_steps_among_successes': {
            'min': min(times) if times else None,
            'median': statistics.median(times) if times else None,
            'max': max(times) if times else None,
        },
        'unconditional_diamond_percent_by_step': {
            str(t): 100*sum(x <= t for x in times)/n
            for t in (100, 200, 400, 800, 1600, 3200, 6400, 10000)
        },
    }
