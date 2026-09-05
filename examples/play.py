"""A complete episode using only the public Crafter API."""
import crafter
from crafter_symbolic import Agent


def main():
    env = crafter.Env(seed=0, length=10000)
    rgb, reward = env.reset(), 0.0
    agent = Agent()
    while True:
        action = agent.act(rgb, reward)
        rgb, reward, done, info = env.step(action)
        if done:
            print(info['achievements'])
            break


if __name__ == '__main__':
    main()
