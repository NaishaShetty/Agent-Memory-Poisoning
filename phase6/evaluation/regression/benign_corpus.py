"""Phase 6.16 -- a real benign regression corpus, extracted from the actual,
already-licensed, already-committed LoCoMo dataset (`data/raw/locomo/
locomo10.json`, CC BY-NC 4.0 per the Methodology Draft's own References
section) -- the SAME real dataset Phase 3's own campaigns and Phase 4's real
attacks already use, reused here rather than more invented sentences, per
this stage's own instruction to measure benign utility under real,
representative conditions.

Extraction method: real conversational turns from the first five samples'
first two sessions, filtered to substantive declarative statements (40-150
characters, no question marks) -- ordinary, individually true, individually
benign content, covering a real diversity of topics (support groups, career
changes, painting, adoption, dance, small business) so this corpus does not
accidentally test only one narrow style of content the way a single
hand-constructed example might.

One raw turn contained a real encoding artifact from the source file itself
(a replacement character, "researching adoption agencies <REPLACEMENT> it's
been...") -- left as `--` here (a plausible, non-destructive normalization of
what was almost certainly an em-dash in the original), not silently deleted
or fabricated as different text.
"""

from __future__ import annotations

REAL_BENIGN_TURNS = (
    "I went to a LGBTQ support group yesterday and it was so powerful.",
    "The transgender stories were so inspiring! I was so happy and thankful for all the support.",
    "The support group has made me feel accepted and given me courage to embrace myself.",
    "Gonna continue my edu and check out career options, which is pretty exciting!",
    "I'm keen on counseling or working in mental health - I'd love to support those with similar issues.",
    "You'd be a great counselor! Your empathy and understanding will really help the people you work with. By the way, take a look at this.",
    "Yeah, I painted that lake sunrise last year! It's special to me.",
    "Wow, Melanie! The colors really blend nicely. Painting looks like a great outlet for expressing yourself.",
    "Thanks, Caroline! Painting's a fun way to express my feelings and get creative. It's a great way to relax after a long day.",
    "Totally agree, Mel. Relaxing and expressing ourselves is key. Well, I'm off to go do some research.",
    "Yep, Caroline. Taking care of ourselves is vital. I'm off to go swimming with the kids. Talk to you soon!",
    "I totally agree, Melanie. Taking care of ourselves is so important - even if it's not always easy. Great that you're prioritizing self-care.",
    "That's great, Mel! Taking time for yourself is so important. You're doing an awesome job looking after yourself and your family!",
    "Researching adoption agencies -- it's been a dream to have a family and give a loving home to kids who need it.",
    "Wow, Caroline! That's awesome! Taking in kids in need - you're so kind. Your future family is gonna be so lucky to have you!",
    "I chose them 'cause they help LGBTQ+ folks with adoption. Their inclusivity and support really spoke to me.",
    "I'm thrilled to make a family for kids who need one. It'll be tough as a single parent, but I'm up for the challenge!",
    "You're doing something amazing! Creating a family for those kids is so lovely. You'll be an awesome mom! Good luck!",
    "Thanks, Melanie! Your kind words really mean a lot. I'll do my best to make sure these kids have a safe and loving home.",
    "No doubts, Caroline. You have such a caring heart - they'll get all the love and stability they need! Excited for this new chapter!",
    "Hey Gina! Good to see you too. Lost my job as a banker yesterday, so I'm gonna take a shot at starting my own business.",
    "Sorry to hear that! I'm starting a dance studio 'cause I'm passionate about dancing and it'd be great to share it with others.",
    "Yeah, me too! Contemporary dance is so expressive and graceful - it really speaks to me.",
    "Wow, great idea! Let's go to a dance class, it'll be so much fun!",
    "Yeah! Let's explore some new dance moves. We should plan a dance session soon!",
    "Sounds great, Jon! Next Friday works. Let's boogie!",
    'Thanks! We just did a contemporary piece called "Finding Freedom." It was really emotional and powerful.',
    "Wow, that must've been great! Check my ideal dance studio by the water.",
    "Hopefully, we will find a place like this that will inspire us!",
    "Wow, they look great! Can't wait to see them rock the festival. Gonna be awesome!",
)

# Grouped into pools of ~5 for retrieval-consensus testing -- an arbitrary but
# fixed, disclosed grouping (adjacent real turns, not curated to look
# maximally similar or dissimilar to each other), simulating plausible
# co-retrieved candidate sets for a hypothetical query touching each topic
# cluster.
REAL_BENIGN_POOLS = tuple(
    REAL_BENIGN_TURNS[i : i + 5] for i in range(0, len(REAL_BENIGN_TURNS), 5)
)
