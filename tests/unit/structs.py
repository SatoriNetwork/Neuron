from satori.concepts.structs import StreamId, StreamIdMap


def testStreamIdMap():
    x0 = StreamId(source='b', author='a', stream='c', target=None)
    x1 = StreamId(source='b', author='a', stream='c', target='d')
    x2 = StreamId(source='b', author='a', stream='c', target='e')
    x3 = StreamId(source='z', author='a', stream='z', target='e')
    x4 = StreamId(source='z', author='a', stream='c', target='e')
    x = StreamIdMap(x0, 0)
    x.addAll([x1, x2, x3, x4], [1, 2, 3, 4])
    assert x.get(x0, greedy=False) == 0
    assert x.get(x0) == 0  # not greedy on get
    assert x.get(x0.new(stream='m'), 'default') == 'default'
    assert x.get(x0.new(stream='m'), 'default', greedy=True) == 'default'
    assert x.get(x0.new(clearStream=True), 'default', greedy=True) == 0
    assert x.get(x0.new(clearStream=True), 'default',
                 greedy=False) == 'default'
    assert x.get(x4.new(clearStream=True), 'default', greedy=True) == 3
    assert x.getAll(x1.new(clearTarget=True), greedy=True) == {
        x0: 0, x1: 1, x2: 2}
    assert x.getAll(x1.new(clearTarget=True), greedy=False) == {x0: 0}
    assert x.getAll(x2.new(clearSource=True), greedy=True) == {x2: 2, x4: 4}
    assert x.isFilled(x1.new(clearTarget=True), greedy=True) == True
    assert x.isFilled(x1.new(clearTarget=True), greedy=False) == True
    assert x.isFilled(x2.new(clearSource=True), greedy=True) == True
    assert x.isFilled(x2.new(author='z'), greedy=True) == False
    assert x.remove(x2.new(author='z'), greedy=True) == []
    assert x.remove(x2.new(clearSource=True), greedy=True) == [x2, x4]
    assert x.getAll(x2.new(clearSource=True), greedy=True) == {}
    assert x.get(x2) == None
