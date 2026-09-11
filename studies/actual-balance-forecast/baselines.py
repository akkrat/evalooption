from runtime import *
if __name__ == '__main__':
    for name, tree in [('base',BASE),('gold',GOLD)]:
        initialize_snapshot(tree)
        for label, args in [('core',['workspace','@actual-app/core','run','test:node']),('web',['workspace','@actual-app/web','run','test'])]:
            output=STUDY/'validation'/f'{name}-all-{label}'
            if not (output/'command.json').exists():
                yarn(tree,args+['--reporter=json','--outputFile='+str(output/'vitest.json'),'--maxWorkers=2'],output,1200)
        for label,args in [('typecheck',['typecheck']),('lint',['lint'])]:
            output=STUDY/'validation'/f'{name}-{label}'
            if not (output/'command.json').exists(): yarn(tree,args,output,1200)
