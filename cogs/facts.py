"""
cogs/facts.py - /facts posts "Sensei! Did you know..." and a random fact (public, anyone can use it).

Add or remove facts by editing FACTS_TEXT below: one fact per line, no numbers.
The same fact is never sent twice in a row.

To limit it to admins and allowed roles like the other commands, add
`from src.role_check import has_allowed_role` and put `@has_allowed_role()`
under the @app_commands.command line.
"""

import random

import discord
from discord import app_commands
from discord.ext import commands

from core.classes import Cog_Extension

FACTS_TEXT = """
Octopuses have three hearts. Two pump blood to the gills, while the third pumps it to the rest of the body.
Bananas are berries, botanically speaking. Strawberries, surprisingly, are not true berries.
A day on Venus is longer than a year on Venus. It takes Venus longer to rotate once than to orbit the Sun.
Sharks are older than trees. Sharks have existed for roughly 400 million years, while the earliest trees appeared around 350 million years ago.
The Eiffel Tower can grow taller in summer. Heat causes its iron to expand.
Wombats produce cube-shaped poop. The unusual shape helps keep it from rolling away when they mark their territory.
The Moon is slowly moving away from Earth. It drifts away at approximately 3.8 centimeters per year.
Honey can remain edible for thousands of years. Its low water content and acidity make it difficult for many microorganisms to grow.
A group of flamingos is called a flamboyance.
Scotland's national animal is the unicorn.
There are more possible ways to shuffle a deck of 52 cards than there are atoms on Earth.
The human nose can distinguish an enormous number of different smells. Estimates vary, but researchers have suggested that it can detect at least a trillion odor combinations.
Dolphins have individual signature whistles. These function somewhat like names.
The shortest war in recorded history lasted between 38 and 45 minutes. It was fought between Britain and Zanzibar in 1896.
Cows have best friends. Research suggests they can form preferred social bonds and experience stress when separated.
The Pacific Ocean is larger than all Earth's land areas combined.
A cloud can weigh hundreds of tonnes. Its water droplets are spread over an enormous volume of air.
Some turtles can breathe through their rear ends. Certain aquatic species absorb oxygen through specialized tissues near their cloaca.
The fingerprints of koalas are remarkably similar to human fingerprints.
There is a species of jellyfish that can potentially reverse its life cycle. Turritopsis dohrnii can return to an earlier developmental stage.
Oxford University is older than the Aztec Empire. Teaching at Oxford dates back to at least 1096, while the Aztec Empire emerged in the 15th century.
The human body contains roughly 37 trillion cells. The exact number varies between individuals.
A bolt of lightning can heat the surrounding air to temperatures hotter than the surface of the Sun.
Penguins propose to potential mates with pebbles. Some species use stones in courtship and nest-building.
The smell after rain has a name: petrichor.
There are lakes beneath Antarctica's ice. Lake Vostok is one of the largest known subglacial lakes.
An adult human has 206 bones. Babies are born with around 270 bones, many of which fuse as they grow.
Sloths can hold their breath for a surprisingly long time. Some can slow their heart rate and remain underwater for up to around 40 minutes.
The world's largest desert is Antarctica. Deserts are defined by low precipitation, not high temperatures.
The first computer mouse was made of wood. It was developed by Douglas Engelbart and his team in the 1960s.
A shrimp's heart is located in its head region.
Some fungi can glow in the dark. This phenomenon is called bioluminescence.
The Great Wall of China is not visible from the Moon with the naked eye. This is a popular myth.
There are more trees on Earth than stars in the Milky Way. Estimates suggest roughly 3 trillion trees versus 100–400 billion stars.
Your stomach lining constantly renews itself. This helps protect it from its own digestive acid.
Butterflies taste with their feet. Special sensors on their feet help them identify suitable plants.
The Amazon rainforest produces a significant amount of its own rainfall. Water released by plants contributes to the regional water cycle.
The fingerprints of identical twins are different. Their DNA is extremely similar, but fingerprints develop through environmental influences before birth.
A blue whale's heart can weigh hundreds of kilograms.
The first known novelist was a woman. Enheduanna, an ancient Mesopotamian poet and priestess, lived around 4,300 years ago, although her surviving works are poetry rather than novels in the modern sense.
There are underwater waterfalls. Some occur when differences in water temperature and density cause one body of water to flow beneath another.
The word "muscle" comes from a Latin word meaning "little mouse."
A group of crows can be called a murder.
Some plants can communicate through chemical signals. They can release airborne compounds in response to insects or other threats.
The human brain uses roughly 20% of the body's energy at rest.
The largest known living organism by area may be a fungus. A honey fungus in Oregon covers several square kilometers.
The Sun accounts for approximately 99.86% of the mass of the solar system.
Sea otters sometimes hold hands while sleeping. This helps them avoid drifting apart.
The ancient Egyptians used moldy bread as part of some wound treatments. They did not understand antibiotics, but certain molds contain compounds that can inhibit bacteria.
There are more than 1,500 active volcanoes worldwide. Many are underwater, and only a fraction are on land.
A single teaspoon of healthy soil can contain millions of microorganisms.
The world's largest flower is the Rafflesia arnoldii. Its bloom can reach about one meter across.
The human eye can distinguish millions of colors. The precise number depends on lighting and individual vision.
Cats cannot taste sweetness in the same way humans can. They lack a functional version of an important sweet-taste receptor.
The first email was sent in 1971. Computer engineer Ray Tomlinson helped introduce the use of the @ symbol in email addresses.
Some frogs freeze during winter and survive. Certain species produce natural compounds that protect their cells during freezing.
The world's deepest known point is Challenger Deep in the Mariana Trench. It is approximately 11 kilometers below sea level.
A day on Jupiter lasts only about 10 hours. Jupiter rotates extremely quickly.
The word "alphabet" comes from the first two letters of the Greek alphabet: alpha and beta.
There are pink lakes. Their color can come from salt-loving microorganisms and pigments.
The first video game console was released in 1972. It was called the Magnavox Odyssey.
Some birds can sleep with one half of their brain at a time. This is called unihemispheric sleep.
The Sahara Desert was once much greener. Thousands of years ago, parts of it had grasslands, lakes, and abundant wildlife.
A snail can have thousands of tiny teeth. They are arranged on a tongue-like structure called a radula.
The human body produces vitamin D when skin is exposed to ultraviolet B sunlight.
There is a species of ant that can make rafts out of its own bodies. Fire ants use this behavior to survive floods.
Saturn could theoretically float in water. Its average density is lower than water's, although no ocean could realistically hold it.
The world's smallest mammal by mass is commonly considered the bumblebee bat. It weighs around 2 grams.
Some trees communicate through underground fungal networks. Fungi connect with plant roots and exchange nutrients and chemical signals.
The first photograph ever taken required an exposure lasting several hours. It was produced by Joseph Nicéphore Niépce around 1826 or 1827.
A rainbow is actually a full circle. From the ground, the horizon usually hides its lower half.
The human skeleton is constantly being remodeled. Old bone tissue is broken down and replaced throughout life.
The oldest known living tree is a bristlecone pine named Methuselah. It is more than 4,800 years old.
A day on Mars is only slightly longer than a day on Earth. It lasts approximately 24 hours and 37 minutes.
Some species of sea cucumber can eject internal organs when threatened. They can later regenerate them.
The word "robot" originated in a 1920 Czech play. It comes from a word associated with forced labor.
There are fish that can climb waterfalls. Some species of gobies use specialized suction structures to move across wet surfaces.
The human body has a natural internal clock. It is known as the circadian rhythm and helps regulate sleep, hormones, and body temperature.
The first modern Olympic Games took place in Athens in 1896.
The Milky Way is on a collision course with the Andromeda Galaxy. They are expected to merge billions of years from now.
Some spiders use electricity to travel through the air. This behavior, called ballooning, allows them to disperse using silk and atmospheric electric fields.
The word "salary" is historically connected to salt. Its exact linguistic history is debated, but it comes from the Latin salarium.
A crocodile cannot stick out its tongue. Its tongue is held in place by a membrane.
The world's largest known animal is the blue whale. It can reach over 30 meters in length.
Your bones are stronger than many people expect. Bone is a living material with a complex structure that combines strength and flexibility.
There are more possible chess games than atoms in the observable universe. Estimates of the number of possible chess games are extraordinarily large.
Some desert plants can remain dormant for years. They can rapidly grow and reproduce when rain finally arrives.
The national flag of Nepal is the only national flag that is not rectangular or square.
The human brain contains approximately 86 billion neurons.
Some sharks glow in the dark. Certain deep-sea species produce blue-green light through bioluminescence.
The world's largest living reptile is the saltwater crocodile. Large males can exceed six meters in length.
The first known mechanical clock was developed in medieval Europe. Early mechanical clocks appeared around the 13th century.
A group of owls is sometimes called a parliament.
There are more than 7,000 living languages worldwide. Many are spoken by relatively small communities.
The Sun is approximately 4.6 billion years old.
A hummingbird is the only group of birds capable of sustained hovering flight. They can also fly backward.
The human heart beats approximately 100,000 times per day. The exact number depends on heart rate and activity.
Some minerals can fluoresce under ultraviolet light. They absorb UV radiation and emit visible light.
The largest organ in the human body is the skin. It acts as a protective barrier and helps regulate body temperature.
The atoms in your body were formed through cosmic processes. Many elements, including carbon, oxygen, and iron, originated in stars or stellar explosions long before Earth existed.
"""

FACTS: list[str] = [line.strip() for line in FACTS_TEXT.splitlines() if line.strip()]


def pick_fact(last: str | None = None, rng=random) -> str:
    """A random fact, never the same one as `last` (unless there is only one)."""
    choices = [fact for fact in FACTS if fact != last] or FACTS
    return rng.choice(choices)


def format_message(fact: str) -> str:
    return f'Sensei! Did you know...\n\n{fact}'


class Facts(Cog_Extension):

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self._last_fact: str | None = None

    @app_commands.command(name='facts', description='Get a random fun fact.')
    async def facts(self, itn: discord.Interaction) -> None:
        self._last_fact = pick_fact(self._last_fact)
        await itn.response.send_message(format_message(self._last_fact))


async def setup(bot: commands.Bot):
    await bot.add_cog(Facts(bot))
