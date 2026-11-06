import os
import random
import re
import sys
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cogs import facts
from cogs.facts import FACTS, Facts, format_message, pick_fact


def test_all_100_facts_are_loaded_without_numbers():
    assert len(FACTS) == 100
    assert not any(re.match(r'^\d+\.\s', fact) for fact in FACTS)
    assert FACTS[0].startswith('Octopuses have three hearts')
    assert FACTS[-1].startswith('The atoms in your body')
    assert len(set(FACTS)) == 100


def test_every_fact_fits_in_a_discord_message():
    assert all(len(format_message(fact)) < 2000 for fact in FACTS)


def test_message_format():
    assert format_message('Cats purr.') == 'Sensei! Did you know...\n\nCats purr.'


def test_never_repeats_the_previous_fact():
    rng = random.Random(1)
    last = None
    for _ in range(500):
        fact = pick_fact(last, rng)
        assert fact != last
        last = fact


def test_all_facts_can_come_up():
    rng = random.Random(7)
    seen = {pick_fact(None, rng) for _ in range(3000)}
    assert len(seen) == 100


async def test_command_sends_publicly():
    cog = Facts(MagicMock())
    itn = MagicMock()
    itn.response.send_message = AsyncMock()
    await cog.facts.callback(cog, itn)
    args, kwargs = itn.response.send_message.await_args
    assert args[0].startswith('Sensei! Did you know...\n\n')
    assert args[0].split('\n\n', 1)[1] in FACTS
    assert 'ephemeral' not in kwargs


def test_facts_command_is_open_to_everyone_and_in_help_order():
    from cogs.help import ORDER
    assert 'facts' in ORDER
    assert not any('allowed_role' in c.__qualname__ for c in Facts.facts.checks)
