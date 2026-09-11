# Scenario, as dictated on 2026-09-11

Speech-to-text slips corrected (route, agent). Nothing else changed.

---

The problem at hand, what I see or what was presented to me, verbatim: a manufacturing
plant operator wants floor supervisors to get answers from the right documentation. The
system should intelligently route to the appropriate source, which could be the safety
procedures, the maintenance manuals or quality control standards, and provide accurate
answers. So that's going to be what we have in front of us.

What we're going to be building is a RAG pipeline. And we're going to make it a
multi-agent sort of build here to have some fun.

We're going to have a user, which would be the floor supervisor, who is going to initiate
the chat. Once that message goes through, it's going to interact with what I will call
agent number one, and that is just going to be our customer service agent. Their job is to
communicate at an understandable, maybe fifth grade level, between the user and our other
agents that I'll talk about next.

Agent B is going to be our safety procedures agent. Their job is to research and get all
information from the safety procedures corpus that we have and pass the answer to the
customer service agent. The same thing with the maintenance manual agent, we're going to
call that agent C. That agent is going to have its domain be the maintenance manuals as
its own operating agent there. The quality control standards is going to be the next
agent, which is agent D. So they are all going to report back to customer service its
findings. That's going to be a total of four agents that are going to be working at the
same time to help the floor supervisor get the accurate answers.

We are going to need LLM evaluation to make sure that we can actually see why each agent
came up with the answer that they came up with. So that's going to be important there.

We are also going to have short-term and long-term memory so that we can see if it's the
same problem that a floor supervisor is having to answer. Or just short-term for this
chat, to be able to save the thread ID and come back to look at what was said and
generated.

How we're going to use it is going to be a chat window. You don't need to build a full-on
front end for it. It's just going to be a chat window that allows us to see the thread.
We're able to refresh the page and have that same thread be open, or hit new chat for
another chat which would have its own thread ID.

The goal is to be able to get this build done using multi-agents within 45 minutes.

Part of my system is that you provide me with a flowchart once you get to that step in
the build, and we're going to open that up using HTML here to be a demonstration for me in
this prototyping example.
